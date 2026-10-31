"""Validation and transactional import of drafted diagnostic flows."""
import json
import warnings
from decimal import Decimal, InvalidOperation

from django.db import transaction

from garage.models import CarModel
from .models import (AnswerOption, Cause, CauseSymptomLink, Question,
                     RepairCost, SelfCheck, Symptom, SymptomCategory)


class ImportErrorInFile(ValueError):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [str(errors)]
        super().__init__("\n".join(self.errors))


VALID_STRENGTHS = {"always", "often", "sometimes", "rarely"}


def _decimal(value, path, errors, minimum=None, maximum=None):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        if minimum is not None and result < minimum or maximum is not None and result > maximum:
            errors.append(f"{path}: must be between {minimum} and {maximum}")
        return result
    except (InvalidOperation, TypeError, ValueError):
        errors.append(f"{path}: must be a number")
        return None


def _items(data, field, errors):
    value = data.get(field, [])
    if not isinstance(value, list):
        errors.append(f"$.{field}: must be an array")
        return []
    return value


def validate_flow(data):
    """Collect structural and database-reference validation errors before writes."""
    errors = []
    if not isinstance(data, dict):
        raise ImportErrorInFile("$: must be a JSON object")
    category = data.get("category")
    if not isinstance(category, dict) or not category.get("name_en"):
        errors.append("$.category.name_en: required")
    symptoms = _items(data, "symptoms", errors)
    causes = _items(data, "causes", errors)
    questions = _items(data, "questions", errors)
    standalone_checks = _items(data, "self_checks", errors)
    seen_keys = set()
    for i, symptom in enumerate(symptoms):
        path = f"$.symptoms[{i}]"
        if not isinstance(symptom, dict):
            errors.append(f"{path}: must be an object")
            continue
        key = symptom.get("key")
        if not isinstance(key, str) or not key:
            errors.append(f"{path}.key: required")
        elif key in seen_keys:
            errors.append(f"{path}.key: duplicate symptom key '{key}'")
        seen_keys.add(key)
        if not (symptom.get("en") or symptom.get("text_en")):
            errors.append(f"{path}.en: required")

    cause_keys = set()
    prior_sum = Decimal("0")
    for i, cause in enumerate(causes):
        path = f"$.causes[{i}]"
        if not isinstance(cause, dict):
            errors.append(f"{path}: must be an object")
            continue
        key = cause.get("key") or cause.get("name")
        if not key:
            errors.append(f"{path}.key: required")
        elif key in cause_keys:
            errors.append(f"{path}.key: duplicate cause key '{key}'")
        cause_keys.add(key)
        prior = _decimal(cause.get("prior", 0.1), f"{path}.prior", errors,
                         Decimal(0), Decimal(1))
        if prior is not None:
            prior_sum += prior
    if causes and not Decimal("0.8") <= prior_sum <= Decimal("1.2"):
        warnings.warn(f"$.causes: priors sum to {prior_sum}, expected 0.8 to 1.2", UserWarning)

    links = data.get("cause_symptom_links")
    # Step 3.1 nests links beneath each cause; retain compatibility with the
    # earlier API's top-level cause_symptom_links shape.
    flat_links = []
    if links is not None:
        flat_links.extend((link, f"$.cause_symptom_links[{i}]")
                          for i, link in enumerate(_items(data, "cause_symptom_links", errors)))
    for i, cause in enumerate(causes):
        if isinstance(cause, dict):
            flat_links.extend((link, f"$.causes[{i}].links[{j}]")
                              for j, link in enumerate(_items(cause, "links", errors)))
    for link, path in flat_links:
        if not isinstance(link, dict):
            errors.append(f"{path}: must be an object")
            continue
        if link.get("cause") not in cause_keys and not any(
                isinstance(c, dict) and c.get("key", c.get("name")) == link.get("cause")
                for c in causes):
            # Nested links may omit cause; their owning cause is set below at import.
            if not (".causes[" in path):
                errors.append(f"{path}.cause: references undefined cause key")
        if link.get("symptom") not in seen_keys:
            errors.append(f"{path}.symptom: references undefined symptom key")
        if link.get("strength") not in VALID_STRENGTHS:
            errors.append(f"{path}.strength: must be one of {sorted(VALID_STRENGTHS)}")
        link_model_name = link.get("car_model")
        if link_model_name:
            link_models = CarModel.objects.select_related("car_make").all()
            link_model_matches = list(link_models.filter(
                car_make__name__iexact=link_model_name.split(" ", 1)[0],
                name__iexact=link_model_name.split(" ", 1)[1]
            )) if " " in link_model_name else list(
                link_models.filter(name__iexact=link_model_name))
            if not link_model_matches:
                errors.append(f"{path}.car_model: no existing model matches '{link_model_name}'")
            elif len(link_model_matches) > 1:
                errors.append(f"{path}.car_model: '{link_model_name}' is ambiguous; specify a unique model")

    for i, question in enumerate(questions):
        path = f"$.questions[{i}]"
        if not isinstance(question, dict):
            errors.append(f"{path}: must be an object")
            continue
        if question.get("symptom") not in seen_keys:
            errors.append(f"{path}.symptom: references undefined symptom key")
        if question.get("type", "single_choice") not in Question.QType.values:
            errors.append(f"{path}.type: must be one of {list(Question.QType.values)}")
        options = question.get("options")
        if not isinstance(options, list) or len(options) < 2:
            errors.append(f"{path}.options: requires at least two options")
            options = options if isinstance(options, list) else []
        unsure = [bool(o.get("unsure", o.get("is_unsure", False)))
                  for o in options if isinstance(o, dict)]
        if len(unsure) != len(options) or sum(unsure) != 1:
            errors.append(f"{path}.options: requires at least two options and exactly one Not sure option (unsure=true)")
        for j, option in enumerate(options):
            if not isinstance(option, dict):
                errors.append(f"{path}.options[{j}]: must be an object")
                continue
            implied = option.get("implies", option.get("implies_symptom"))
            if implied is not None and implied not in seen_keys:
                errors.append(f"{path}.options[{j}].implies: references undefined symptom key")

    costs = []
    for i, cause in enumerate(causes):
        if isinstance(cause, dict):
            self_check = cause.get("self_check", [])
            checks = [self_check] if isinstance(self_check, dict) else self_check
            for j, check in enumerate(checks):
                if not isinstance(check, dict):
                    errors.append(f"$.causes[{i}].self_check[{j}]: must be an object")
            costs.extend((cost, f"$.causes[{i}].costs[{j}]")
                         for j, cost in enumerate(_items(cause, "costs", errors)))
    costs.extend((cost, f"$.repair_costs[{i}]")
                 for i, cost in enumerate(_items(data, "repair_costs", errors)))
    for cost, path in costs:
        if not isinstance(cost, dict):
            errors.append(f"{path}: must be an object")
            continue
        if cost.get("cause") not in cause_keys and not any(
                isinstance(c, dict) and c.get("key", c.get("name")) == cost.get("cause")
                for c in causes):
            if ".causes[" not in path:
                errors.append(f"{path}.cause: references undefined cause key")
        for low, high in (("parts_min", "parts_max"), ("labour_min", "labour_max")):
            if low in cost and high in cost:
                try:
                    low_value = Decimal(str(cost[low]))
                    high_value = Decimal(str(cost[high]))
                    if low_value < 0 or high_value < 0:
                        errors.append(f"{path}.{low}: costs must be non-negative")
                    if low_value > high_value:
                        errors.append(f"{path}.{low}: must be <= {high}")
                except (InvalidOperation, TypeError, ValueError):
                    errors.append(f"{path}.{low}: cost bounds must be numbers")

    for i, check in enumerate(standalone_checks):
        path = f"$.self_checks[{i}]"
        if not isinstance(check, dict):
            errors.append(f"{path}: must be an object")
            continue
        if check.get("cause") not in cause_keys:
            errors.append(f"{path}.cause: references undefined cause key")
        if not (check.get("steps") or check.get("steps_en") or check.get("en")):
            errors.append(f"{path}.steps: required")
        if check.get("difficulty", "easy") not in SelfCheck.Difficulty.values:
            errors.append(f"{path}.difficulty: must be one of {list(SelfCheck.Difficulty.values)}")

    models_data = data.get("car_models", [])
    if not isinstance(models_data, list):
        errors.append("$.car_models: must be an array")
        models_data = []
    resolved_models = {}
    for i, name in enumerate(models_data):
        if not isinstance(name, str):
            errors.append(f"$.car_models[{i}]: must be a model name")
            continue
        query = CarModel.objects.select_related("car_make").all()
        exact_make_model = " " in name
        if exact_make_model:
            make_name, model_name = name.split(" ", 1)
            matches = list(query.filter(car_make__name__iexact=make_name,
                                        name__iexact=model_name))
        else:
            matches = list(query.filter(name__iexact=name))
        if not matches:
            errors.append(f"$.car_models[{i}]: no existing model matches '{name}'")
        elif len(matches) > 1 and not exact_make_model:
            errors.append(f"$.car_models[{i}]: '{name}' is ambiguous; use 'Make Model'")
        else:
            # A make+model selector can legitimately refer to several
            # generations stored as separate CarModel rows. Associate all of
            # them with the flow; only a model-only selector must be unique.
            resolved_models[name] = matches
    if errors:
        raise ImportErrorInFile(errors)
    return {"category": category, "symptoms": symptoms, "causes": causes,
            "questions": questions, "self_checks": standalone_checks,
            "links": flat_links, "costs": costs,
            "models": resolved_models}


def _upsert(model, lookup, defaults, counts, *, owner=None, draft_owner=False):
    obj = model.objects.filter(**lookup).first()
    if obj and obj.status in {"approved", "published"}:
        counts["skipped"] += 1
        return obj, False
    created = obj is None
    if created:
        obj = model(**lookup)
    for field, value in defaults.items():
        setattr(obj, field, value)
    obj.status = "draft" if draft_owner else "ai_draft"
    obj.is_dummy = not draft_owner
    obj.created_by = owner if draft_owner else None
    obj.save()
    counts["created" if created else "updated"] += 1
    return obj, True


@transaction.atomic
def import_flow(data, user=None, dry_run=False, draft_owner=False):
    if isinstance(data, (str, bytes)):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ImportErrorInFile(f"$: invalid JSON: {exc}") from exc
    validated = validate_flow(data)
    counts = {"created": 0, "updated": 0, "skipped": 0}
    cat_data = validated["category"]
    category, _ = SymptomCategory.objects.get_or_create(
        name_en=cat_data["name_en"], defaults={
            "name_roman": cat_data.get("name_roman", cat_data.get("roman", "")),
            "name_ur": cat_data.get("name_ur", "")})
    SymptomCategory.objects.filter(pk=category.pk).update(
        name_roman=cat_data.get("name_roman", cat_data.get("roman", "")),
        name_ur=cat_data.get("name_ur", ""))
    symptoms, causes = {}, {}
    for symptom in validated["symptoms"]:
        key = symptom["key"]
        obj, writable = _upsert(Symptom, {"category": category, "key": key}, {
            "text_en": symptom.get("en", symptom.get("text_en")),
            "text_roman": symptom.get("roman", symptom.get("text_roman", "")),
            "text_ur": symptom.get("ur", symptom.get("text_ur", "")),
            "is_safety_critical": symptom.get("safety", symptom.get("is_safety_critical", False)),
        }, counts, owner=user, draft_owner=draft_owner)
        symptoms[key] = obj
    for cause_data in validated["causes"]:
        key = cause_data.get("key", cause_data.get("name"))
        name = cause_data.get("name", key)
        obj, writable = _upsert(Cause, {"name": name}, {
            "system": cause_data.get("system", ""),
            "description": cause_data.get("description", ""),
            "proof_hint": cause_data.get(
                "proof_hint", "Ask which part is worn and ask to see it. You can also ask for the old part back."),
            "prior": Decimal(str(cause_data.get("prior", "0.1"))),
            "severity": cause_data.get("severity", "medium"),
            "safe_to_drive": cause_data.get("safe_to_drive", True),
        }, counts, owner=user, draft_owner=draft_owner)
        causes[key] = (obj, writable)
        if writable:
            linked_models = [model for matches in validated["models"].values()
                             for model in matches]
            obj.car_models.set(linked_models)

    for link, path in validated["links"]:
        nested = ".causes[" in path
        if nested:
            import re
            match = re.search(r"\$\.causes\[(\d+)\]", path)
            owner = validated["causes"][int(match.group(1))]
            cause_key = owner.get("key", owner.get("name"))
        else:
            cause_key = link["cause"]
        cause, cause_writable = causes[cause_key]
        symptom = symptoms[link["symptom"]]
        if not cause_writable or symptom.status in {"approved", "published"}:
            counts["skipped"] += 1
            continue
        model_name = link.get("car_model")
        model_matches = validated["models"].get(model_name, [])
        model = model_matches[0] if len(model_matches) == 1 else None
        _link_obj, link_created = CauseSymptomLink.objects.update_or_create(
            cause=cause, symptom=symptom, car_model=model,
            defaults={"strength": link["strength"]})
        counts["created" if link_created else "updated"] += 1

    for question_data in validated["questions"]:
        symptom = symptoms[question_data["symptom"]]
        text = question_data.get("en", question_data.get("text_en"))
        question, writable = _upsert(Question, {"symptom": symptom, "text_en": text}, {
            "text_roman": question_data.get("roman", question_data.get("text_roman", "")),
            "text_ur": question_data.get("ur", question_data.get("text_ur", "")),
            "type": question_data.get("type", "single_choice"),
            "media_url": question_data.get("media_url", ""),
        }, counts, owner=user, draft_owner=draft_owner)
        if writable:
            for option in question_data["options"]:
                implied = option.get("implies", option.get("implies_symptom"))
                _option, option_created = AnswerOption.objects.update_or_create(
                    question=question,
                    label=option.get("en", option.get("label", option.get("label_en", ""))),
                    defaults={
                        "label_roman": option.get("roman", option.get("label_roman", "")),
                        "is_unsure": option.get("unsure", option.get("is_unsure", False)),
                        "implies_symptom": symptoms.get(implied) if implied else None})
                counts["created" if option_created else "updated"] += 1
            question.options.exclude(label__in=[
                option.get("en", option.get("label", option.get("label_en", "")))
                for option in question_data["options"]]).delete()

    for cause_data in validated["causes"]:
        cause_key = cause_data.get("key", cause_data.get("name"))
        cause, cause_writable = causes[cause_key]
        if not cause_writable:
            counts["skipped"] += len(cause_data.get("self_check", []))
            counts["skipped"] += len(cause_data.get("costs", []))
            continue
        raw_self = cause_data.get("self_check", [])
        if isinstance(raw_self, dict):
            raw_self = [raw_self]
        for check in raw_self:
            steps = check.get("en", check.get("steps_en", check.get("steps", "")))
            roman = check.get("roman", check.get("steps_roman", ""))
            if roman:
                steps += "\n\nRoman Urdu:\n" + roman
            _upsert(SelfCheck, {"cause": cause}, {
                "steps": steps, "tools_needed": check.get("tools_needed", ""),
                "difficulty": check.get("difficulty", "easy")}, counts,
                owner=user, draft_owner=draft_owner)
        for cost in cause_data.get("costs", []):
            _import_cost(cause, cost, counts, owner=user, draft_owner=draft_owner)
    for check in validated["self_checks"]:
        cause = causes[check["cause"]][0]
        steps = check.get("steps", check.get("steps_en", check.get("en", "")))
        roman = check.get("roman", check.get("steps_roman", ""))
        if roman:
            steps += "\n\nRoman Urdu:\n" + roman
        _upsert(SelfCheck, {"cause": cause}, {
            "steps": steps, "tools_needed": check.get("tools_needed", ""),
            "difficulty": check.get("difficulty", "easy")}, counts,
            owner=user, draft_owner=draft_owner)
    # Legacy top-level collections remain supported.
    for cost, path in validated["costs"]:
        if path.startswith("$.repair_costs["):
            _import_cost(causes[cost["cause"]][0], cost, counts,
                         owner=user, draft_owner=draft_owner)

    if dry_run:
        transaction.set_rollback(True)
    return counts


def _import_cost(cause, cost, counts, *, owner=None, draft_owner=False):
    _upsert(RepairCost, {"cause": cause, "city": cost.get("city", "Pakistan (average)")}, {
        "parts_min": cost.get("parts_min", 0), "parts_max": cost.get("parts_max", 0),
        "labour_min": cost.get("labour_min", 0), "labour_max": cost.get("labour_max", 0),
        "last_verified": cost.get("last_verified") or None, "source": "ai_draft",
    }, counts, owner=owner, draft_owner=draft_owner)

