from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from knowledge.importer import ImportErrorInFile, import_flow, validate_flow
from knowledge.models import (
    AnswerOption, Cause, CauseSymptomLink, Question, RepairCost, SelfCheck,
    Status, Symptom, SymptomCategory,
)
from knowledge.services.workflow import claim


def editable_items(queryset, user):
    return queryset.filter(
        Q(created_by=user) |
        Q(created_by__isnull=True, status__in=[Status.AI_DRAFT, Status.DRAFT])
    )


def can_edit(item, user):
    if getattr(item, "created_by_id", None) == user.pk:
        return True
    return (getattr(item, "created_by_id", None) is None and
            getattr(item, "status", None) in {Status.AI_DRAFT, Status.DRAFT})


def require_editable(item, user):
    if not can_edit(item, user):
        raise NotFound("Content not found.")
    if getattr(item, "status", None) not in {Status.AI_DRAFT, Status.DRAFT}:
        raise ValidationError("Only draft content can be edited by mechanics.")
    if getattr(item, "created_by_id", None) is None:
        claim(item, user)
        item.refresh_from_db()
    return item


def _check_ownership(obj, user):
    if obj is None:
        return
    require_editable(obj, user)


def _preflight_flow(data, user, category=None):
    validated = validate_flow(data)
    cat_data = validated["category"]
    if category and category.name_en != cat_data["name_en"]:
        raise ValidationError({"category": "Flow category cannot be renamed."})
    if category is None:
        category = SymptomCategory.objects.filter(
            name_en=cat_data["name_en"]).first()
    if category:
        keys = [item["key"] for item in validated["symptoms"]]
        for symptom in Symptom.objects.filter(category=category, key__in=keys):
            _check_ownership(symptom, user)

    cause_names = [item.get("name", item.get("key")) for item in validated["causes"]]
    existing_causes = {cause.name: cause for cause in Cause.objects.filter(name__in=cause_names)}
    for cause in existing_causes.values():
        _check_ownership(cause, user)
        _check_ownership(cause.self_checks.order_by("pk").first(), user)
        for cost in cause.costs.all():
            _check_ownership(cost, user)

    if category:
        symptoms_by_key = {s.key: s for s in Symptom.objects.filter(
            category=category, key__in=[x["key"] for x in validated["symptoms"]])}
        for question_data in validated["questions"]:
            symptom = symptoms_by_key.get(question_data["symptom"])
            if symptom:
                text = question_data.get("en", question_data.get("text_en"))
                question = Question.objects.filter(symptom=symptom, text_en=text).first()
                _check_ownership(question, user)

    # Link and option objects are not independently governed; the ownership of
    # their parent cause/question controls whether the import can change them.
    for link, _path in validated["links"]:
        cause_ref = link.get("cause")
        if cause_ref:
            cause = existing_causes.get(cause_ref)
            _check_ownership(cause, user)

    if category is None and SymptomCategory.objects.filter(
            name_en=cat_data["name_en"]).exists():
        raise ValidationError({"category": "This flow is not available to your account."})
    return validated, category


@transaction.atomic
def save_flow(data, user, category=None):
    _preflight_flow(data, user, category)
    try:
        import_flow(data, user=user, draft_owner=True)
    except ImportErrorInFile as exc:
        raise ValidationError({"flow": exc.errors}) from exc
    category = SymptomCategory.objects.get(name_en=data["category"]["name_en"])
    owned_symptoms = Symptom.objects.filter(category=category, created_by=user)
    causes = Cause.objects.filter(created_by=user,
                                  name__in=[c.get("name", c.get("key"))
                                            for c in data.get("causes", [])])
    for item in list(owned_symptoms) + list(causes):
        if item.status != Status.DRAFT:
            item.status = Status.DRAFT
            item.save(update_fields=["status", "updated_at"])
    return category


def flow_queryset(user):
    category_ids = Symptom.objects.filter(created_by=user).values("category_id")
    return SymptomCategory.objects.filter(pk__in=category_ids).distinct().order_by("name_en")


def flow_data(category, user):
    symptoms = list(Symptom.objects.filter(category=category).filter(
        Q(created_by=user) |
        Q(created_by__isnull=True, status__in=[Status.AI_DRAFT, Status.DRAFT])
    ).order_by("pk"))
    symptom_keys = {s.pk: s.key for s in symptoms}
    causes = list(Cause.objects.filter(
        Q(created_by=user, links__symptom__in=symptoms) |
        Q(created_by__isnull=True, status__in=[Status.AI_DRAFT, Status.DRAFT],
          links__symptom__in=symptoms)).distinct().order_by("pk"))
    return {
        "id": category.pk,
        "category": {"name_en": category.name_en,
                     "name_roman": category.name_roman,
                     "name_ur": category.name_ur},
        "symptoms": [{"id": s.pk, "key": s.key, "en": s.text_en,
                      "roman": s.text_roman, "ur": s.text_ur,
                      "safety": s.is_safety_critical, "status": s.status}
                     for s in symptoms],
        "causes": [{
            "id": cause.pk, "name": cause.name, "system": cause.system,
            "description": cause.description, "prior": str(cause.prior),
            "severity": cause.severity, "safe_to_drive": cause.safe_to_drive,
            "links": [{"symptom": symptom_keys.get(link.symptom_id),
                       "strength": link.strength}
                      for link in cause.links.filter(symptom__in=symptoms)],
            "self_checks": [{"steps": check.steps,
                             "tools_needed": check.tools_needed,
                             "difficulty": check.difficulty,
                             "status": check.status}
                            for check in cause.self_checks.all()],
            "costs": [{"city": cost.city, "parts_min": cost.parts_min,
                       "parts_max": cost.parts_max, "labour_min": cost.labour_min,
                       "labour_max": cost.labour_max,
                       "last_verified": cost.last_verified,
                       "status": cost.status}
                      for cost in cause.costs.all()],
        } for cause in causes],
        "questions": [{
            "id": q.pk, "symptom": q.symptom.key, "text_en": q.text_en,
            "text_roman": q.text_roman, "type": q.type,
            "options": [{"label": option.label,
                         "label_roman": option.label_roman,
                         "is_unsure": option.is_unsure,
                         "implies_symptom": (option.implies_symptom.key
                                             if option.implies_symptom_id else None)}
                        for option in q.options.all()],
        } for q in Question.objects.filter(symptom__in=symptoms)],
    }


@transaction.atomic
def delete_flow(category, user):
    data = flow_data(category, user)
    own_symptoms = Symptom.objects.filter(category=category, created_by=user)
    symptom_ids = list(own_symptoms.values_list("pk", flat=True))
    own_questions = Question.objects.filter(symptom_id__in=symptom_ids,
                                            created_by=user)
    own_questions.delete()
    own_symptoms.delete()
    for cause in Cause.objects.filter(created_by=user):
        cause.links.filter(symptom_id__in=symptom_ids).delete()
        if not cause.links.exists():
            cause.delete()
    if not Symptom.objects.filter(category=category).exists():
        category.delete()
    return data


def flow_progress(category, user):
    symptoms = Symptom.objects.filter(category=category, created_by=user)
    causes = Cause.objects.filter(created_by=user, links__symptom__in=symptoms).distinct()
    pieces = {
        "category": True,
        "symptoms": symptoms.exists(),
        "causes": causes.exists(),
        "links": CauseSymptomLink.objects.filter(
            cause__in=causes, symptom__in=symptoms).exists(),
        "questions": Question.objects.filter(symptom__in=symptoms,
                                               created_by=user).exists(),
        "self_checks": SelfCheck.objects.filter(cause__in=causes,
                                                  created_by=user).exists(),
        "costs": RepairCost.objects.filter(cause__in=causes,
                                            created_by=user).exists(),
    }
    complete = sum(pieces.values())
    return {"percentage": round(100 * complete / len(pieces)), "pieces": pieces}


GOVERNED_TYPES = {
    "symptoms": Symptom,
    "causes": Cause,
    "self-checks": SelfCheck,
    "repair-costs": RepairCost,
    "questions": Question,
}
RELATION_TYPES = {"links": CauseSymptomLink, "options": AnswerOption}
