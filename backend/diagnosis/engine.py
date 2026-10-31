"""Rules-based diagnosis scoring, safety checks, and question selection."""
from decimal import Decimal
import math

from django.conf import settings
from django.db.models import Prefetch, Q

from diagnosis.models import SessionAnswer, SessionSymptom
from knowledge.models import (AnswerEffect, AnswerOption, Cause, CauseSymptomLink, Question,
                              Status, Symptom)


SAFETY_MESSAGE_KEY = "diagnosis.safety.stop_driving"
CONFIRMS, DENIES = AnswerEffect.CONFIRMS, AnswerEffect.DENIES  # noqa: F821

def _entropy(ps):
    total = sum(ps)
    if total <= 0:
        return 0.0
    return -sum((p / total) * math.log2(p / total) for p in ps if p > 0)

def _info_gain(probs, likelihoods):
    yes = [p * l for p, l in zip(probs, likelihoods)]
    no = [p * (1 - l) for p, l in zip(probs, likelihoods)]
    p_yes, p_no = sum(yes), sum(no)
    if p_yes < 1e-6 or p_no < 1e-6:
        return 0.0
    return _entropy(probs) - (p_yes * _entropy(yes) + p_no * _entropy(no))

def _symptom_label(symptom, language):
    if language == "roman_ur" and symptom.text_roman:
        return symptom.text_roman
    return symptom.text_en


def _answer_wording(answer, language):
    if answer.free_text:
        return answer.free_text
    option = answer.option
    if language == "roman_ur" and getattr(option, "label_roman", ""):
        return option.label_roman
    return getattr(option, "label", "")


def _visible(queryset, include_drafts=None):
    if include_drafts is True:
        return queryset.exclude(status=Status.REJECTED)
    if include_drafts is False:
        return queryset.filter(status=Status.PUBLISHED, is_dummy=False)
    return queryset.visible()


def evidence(session, include_drafts=None):
    """Present/absent symptom evidence. Driven by option.effect, not implies_symptom.

    confirms -> present, denies -> absent, context/unsure -> no symptom evidence.
    The latest answer for a symptom wins; free-text-mapped symptoms count as present.
    """
    answers = list(session.answers.select_related(
        "option", "option__implies_symptom", "question__symptom"
    ).order_by("answered_at", "id"))
    free_text_symptoms = list(session.session_symptoms.select_related(
        "symptom").order_by("created_at", "id"))

    def target_id(answer):
        return answer.option.implies_symptom_id or answer.question.symptom_id

    symptom_ids = {target_id(a) for a in answers if a.option.effect in (CONFIRMS, DENIES)}
    symptom_ids.update(item.symptom_id for item in free_text_symptoms)
    visible = {s.pk: s for s in _visible(Symptom.objects, include_drafts).filter(  # noqa: F821
        pk__in=symptom_ids, category_id=session.category_id)}

    language = getattr(session.user, "language", "en")
    present, absent = {}, {}
    for answer in answers:
        if answer.option.effect not in (CONFIRMS, DENIES):
            continue
        symptom = visible.get(target_id(answer))
        if not symptom:
            continue
        entry = {"symptom": symptom, "answer": answer,
                 "wording": _answer_wording(answer, language)}  # noqa: F821
        if answer.option.effect == CONFIRMS:
            present[symptom.pk] = entry
            absent.pop(symptom.pk, None)
        else:
            absent[symptom.pk] = entry
            present.pop(symptom.pk, None)
    for item in free_text_symptoms:
        symptom = visible.get(item.symptom_id)
        if symptom:
            present[symptom.pk] = {"symptom": symptom, "answer": item,
                                   "wording": _symptom_label(symptom, language)}  # noqa: F821
            absent.pop(symptom.pk, None)
    return {"present": present, "absent": absent}


def context_facts(session):
    """{'when': ['idle'], 'frequency': ['sometimes'], ...} for this session."""
    facts = {}
    for fact in session.context_facts.order_by("created_at", "id"):
        facts.setdefault(fact.key, []).append(fact.value)
    return facts

def confirmed_symptoms(session, include_drafts=None):
    """Compatibility helper returning the session's visible present symptoms."""
    return {pk: item["symptom"] for pk, item in
            evidence(session, include_drafts)["present"].items()}


def _candidate_causes(session, symptoms=None, include_drafts=None):
    """Fetch category and vehicle causes plus their relevant links in two queries."""
    if session.category_id is None:
        return []
    category_symptoms = _visible(Symptom.objects, include_drafts).filter(
        category_id=session.category_id)
    if symptoms is not None:
        category_symptoms = category_symptoms.filter(pk__in=symptoms)
    car_model_id = session.car.car_model_id
    relevant_links = (CauseSymptomLink.objects
                      .filter(symptom__in=category_symptoms)
                      .filter(Q(car_model__isnull=True) |
                              Q(car_model_id=car_model_id))
                      .select_related("symptom"))
    causes = (_visible(Cause.objects, include_drafts)
              .filter(links__symptom__in=category_symptoms)
              .filter(Q(car_models__isnull=True) |
                      Q(car_models__id=car_model_id))
              .distinct()
              .prefetch_related(Prefetch("links", queryset=relevant_links)))
    if session.obd_code_id:
        causes = causes.filter(obd_code_links__obd_code_id=session.obd_code_id)
    return list(causes)


def _weight_map(causes, symptom_ids, car_model_id):
    """Fetch applicable links once; a model-specific rule overrides generic."""
    cause_ids = [cause.pk for cause in causes]
    if not cause_ids or not symptom_ids:
        return {}
    links = (CauseSymptomLink.objects
             .filter(cause_id__in=cause_ids, symptom_id__in=symptom_ids)
             .filter(Q(car_model__isnull=True) | Q(car_model_id=car_model_id)))
    weights = {}
    generic = {}
    for link in links:
        key = (link.cause_id, link.symptom_id)
        if link.car_model_id == car_model_id:
            weights[key] = float(link.weight)
        else:
            generic[key] = float(link.weight)
    for key, weight in generic.items():
        weights.setdefault(key, weight)
    return weights

def rank_causes(session, top=5, include_drafts=None):
    """Rank visible causes in log space and explain evidence for each result."""
    observations = evidence(session, include_drafts)
    present = observations["present"]
    absent = observations["absent"]
    all_evidence = {**present, **absent}
    causes = _candidate_causes(session, include_drafts=include_drafts)
    if not causes:
        return []

    model_id = session.car.car_model_id
    weights = _weight_map(causes, all_evidence.keys(), model_id)
    leak = min(max(float(settings.ENGINE_LEAK_LIKELIHOOD), 1e-12), 1 - 1e-12)
    log_scores = []
    for cause in causes:
        prior = float(cause.prior)
        score = math.log(prior) if prior > 0 else float("-inf")
        for symptom_id in present:
            likelihood = weights.get((cause.pk, symptom_id), leak)
            score += math.log(max(likelihood, 1e-12))
        for symptom_id in absent:
            likelihood = 1 - weights.get((cause.pk, symptom_id), leak)
            score += math.log(max(likelihood, 1e-12))
        log_scores.append((score, cause))

    log_scores.sort(key=lambda item: item[0], reverse=True)
    selected = log_scores if top is None else log_scores[:max(0, top)]
    if not selected:
        return []
    max_score = max(score for score, _ in selected)
    if max_score == float("-inf"):
        return []
    exponentials = [math.exp(score - max_score) for score, _ in selected]
    total = sum(exponentials)
    probabilities = [value / total for value in exponentials]
    rounded_confidences = [Decimal(f"{value:.6f}") for value in probabilities]
    rounded_confidences[0] += Decimal("1.000000") - sum(rounded_confidences)

    language = getattr(session.user, "language", "en")
    results = []
    for rank, ((_, cause), confidence) in enumerate(
            zip(selected, rounded_confidences), start=1):
        supporting = []
        contradicting = []
        for symptom_id, item in present.items():
            if (cause.pk, symptom_id) in weights:
                supporting.append({
                    "symptom": _symptom_label(item["symptom"], language),
                    "answer": item["wording"],
                })
            else:
                contradicting.append({
                    "symptom": _symptom_label(item["symptom"], language),
                    "answer": item["wording"],
                })
        for symptom_id, item in absent.items():
            if (cause.pk, symptom_id) in weights:
                contradicting.append({
                    "symptom": _symptom_label(item["symptom"], language),
                    "answer": item["wording"],
                })
        missing = set()
        for link in cause.links.all():
            if link.symptom_id not in all_evidence:
                missing.add(_symptom_label(link.symptom, language))
        explanation_parts = []
        if supporting:
            explanation_parts.append("Supported by " + ", ".join(
                entry["answer"] or entry["symptom"] for entry in supporting))
        if contradicting:
            explanation_parts.append("Not supported by " + ", ".join(
                entry["answer"] or entry["symptom"] for entry in contradicting))
        results.append({
            "cause": cause,
            "rank": rank,
            "confidence": confidence,
            "explanation": ". ".join(explanation_parts) + "."
            if explanation_parts else "No symptom answers have been recorded yet.",
            "supporting_symptoms": supporting,
            "contradicting_symptoms": contradicting,
            "missing_symptoms": sorted(missing),
        })
    return results


def safety_alert(session, current_answer=None, include_drafts=None):
    """Return the first visible safety symptom and its localized message key."""
    present = evidence(session, include_drafts)["present"]
    if current_answer is not None:
        option = question = None
        free_text = ""
        if isinstance(current_answer, Symptom):
            candidate = current_answer
        else:
            if isinstance(current_answer, AnswerOption):
                option = current_answer
            elif isinstance(current_answer, SessionAnswer):
                option = current_answer.option
                question = current_answer.question
                free_text = current_answer.free_text
            elif isinstance(current_answer, dict):
                option = current_answer.get("option")
                question = current_answer.get("question")
                free_text = current_answer.get("free_text", "")
            else:
                option = getattr(current_answer, "option", None)
                question = getattr(current_answer, "question", None)
            if isinstance(option, int):
                option = AnswerOption.objects.select_related(
                    "implies_symptom", "question__symptom").filter(pk=option).first()
            if isinstance(question, int):
                question = Question.objects.select_related("symptom").filter(
                    pk=question).first()
            if option and question is None:
                question = option.question
            if option and option.effect == CONFIRMS:
                candidate = option.implies_symptom or (question.symptom if question else None)
            else:
                candidate = None

        if candidate and candidate.pk not in present:
            candidate = _visible(Symptom.objects, include_drafts).filter(
                pk=candidate.pk, category_id=session.category_id).first()
        if candidate and candidate.is_safety_critical:
            return {"symptom": candidate, "message_key": SAFETY_MESSAGE_KEY,
                    "answer": free_text}

    for item in present.values():
        symptom = item["symptom"]
        if symptom.is_safety_critical:
            return {"symptom": symptom, "message_key": SAFETY_MESSAGE_KEY,
                    "answer": item["wording"]}
    return None


def next_question(session, ranked=None, include_drafts=None):
    if ranked is None:
        ranked = rank_causes(session, top=5, include_drafts=include_drafts)
    ranked = [item for item in ranked if item.get("cause")][:5]
    causes = [item["cause"] for item in ranked]
    if not causes:
        return None

    observations = evidence(session, include_drafts)
    present = set(observations["present"])
    determined = present | set(observations["absent"])

    relevant_symptoms = None
    if session.obd_code_id:
        relevant_symptoms = CauseSymptomLink.objects.filter(
            cause__obd_code_links__obd_code_id=session.obd_code_id,
            cause__in=[cause.pk for cause in causes],
            symptom__category_id=session.category_id,
        ).values("symptom_id")

    base = (_visible(Question.objects, include_drafts).filter(
        symptom__in=_visible(Symptom.objects, include_drafts).filter(
            category_id=session.category_id))
        .exclude(pk__in=session.answers.values("question_id"))
        .select_related("symptom"))
    if relevant_symptoms is not None:
        base = base.filter(symptom_id__in=relevant_symptoms)

    # 1. Context follow-ups (unchanged)
    asked_context = session.answers.filter(question__is_context=True).count()
    if asked_context < settings.ENGINE_MAX_CONTEXT_QUESTIONS:
        follow_up = (base.filter(is_context=True)
                     .filter(Q(requires_symptom__in=present) |
                             Q(requires_symptom__isnull=True, symptom_id__in=present))
                     .order_by("id").first())
        if follow_up:
            return follow_up

    # 2. Curated entry questions, only while there is no evidence yet
    if not present:
        triage = (base.filter(is_triage=True, is_context=False)
                  .exclude(symptom_id__in=determined)
                  .order_by("triage_order", "id").first())
        if triage:
            return triage

    # 3. Diagnostic questions by information gain
    questions = list(base.filter(is_context=False, symptom__is_observable=True,
                                 symptom__is_generic=False)
                     .filter(Q(requires_symptom__isnull=True) |
                             Q(requires_symptom__in=present))
                     .exclude(symptom_id__in=determined).order_by("id"))
    if not questions:
        return None

    weights = _weight_map(causes, {q.symptom_id for q in questions},
                          session.car.car_model_id)
    leak = float(settings.ENGINE_LEAK_LIKELIHOOD)
    probs = [float(item["confidence"]) for item in ranked]
    best, best_gain = None, 1e-6
    for question in questions:
        likelihoods = [weights.get((c.pk, question.symptom_id), leak) for c in causes]
        gain = _info_gain(probs, likelihoods)
        if gain > best_gain:
            best, best_gain = question, gain

    if best is None and not present:
        # No evidence yet: pick the question most linked to the leading causes,
        # never an unrelated one. If nothing is linked at all, ask nothing.
        scored = [
            (sum(p * weights.get((c.pk, q.symptom_id), 0.0)
                 for p, c in zip(probs, causes)), q)
            for q in questions
        ]
        top_score, top_question = max(scored, key=lambda item: item[0])
        return top_question if top_score > 0 else None
    return best

def should_stop(session, ranked, include_drafts=None):
    """Confidence/margin stop, or budget stop. Context follow-ups don't use the budget."""
    top = float(ranked[0]["confidence"]) if ranked else 0.0
    second = float(ranked[1]["confidence"]) if len(ranked) > 1 else 0.0
    if top >= settings.ENGINE_CONFIDENCE_THRESHOLD and top - second >= settings.ENGINE_MIN_GAP:  # noqa: F821
        return True
    if session.answers.filter(question__is_context=False).count() >= settings.ENGINE_MAX_QUESTIONS:  # noqa: F821
        return True
    return next_question(session, ranked, include_drafts=include_drafts) is None

  