"""Run a diagnosis with temporary answers and no persisted session records."""
from types import SimpleNamespace

from diagnosis.engine import (_visible, evidence, next_question, rank_causes,
                              safety_alert)
from knowledge.models import Symptom


class _RelatedList:
    """Small related-manager adapter for the rules engine's read-only methods."""
    def __init__(self, rows=()):
        self.rows = list(rows)

    def select_related(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def values(self, field):
        return [getattr(row, field) for row in self.rows]

    def count(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)


class _SimulationSession:
    """Session-shaped, non-model object accepted by diagnosis.engine."""
    def __init__(self, *, car_model_id, category_id, user, answers):
        self.car = SimpleNamespace(car_model_id=car_model_id)
        self.category_id = category_id
        self.user = user
        self.answers = _RelatedList(answers)
        self.session_symptoms = _RelatedList()


def _localized_question(question, user):
    roman = getattr(user, "language", "en") == "roman_ur"
    return {
        "id": question.pk,
        "text": question.text_roman if roman and question.text_roman else question.text_en,
        "type": question.type,
        "media_url": question.media_url,
        "options": [{
            "id": option.pk,
            "label": option.label_roman if roman and option.label_roman else option.label,
            "is_unsure": option.is_unsure,
        } for option in question.options.all()],
    }


def simulate(*, car_model, category, user, answers, include_drafts=True, top=5):
    """Run engine ranking for submitted option IDs without writing any rows.

    ``answers`` is a sequence of dictionaries with ``question`` and ``option``
    model objects. The adapter is deliberately not a DiagnosisSession model.
    """
    rows = [SimpleNamespace(
        id=index,
        question=item["question"],
        question_id=item["question"].pk,
        option=item["option"],
        option_id=item["option"].pk,
        free_text=item.get("free_text", ""),
        answered_at=index,
    ) for index, item in enumerate(answers, start=1)]
    session = _SimulationSession(car_model_id=car_model.pk,
                                 category_id=category.pk,
                                 user=user, answers=rows)
    alert = safety_alert(session, include_drafts=include_drafts)
    if alert:
        symptom = alert["symptom"]
        label = (symptom.text_roman or symptom.text_en
                 if user.language == "roman_ur" else symptom.text_en)
        return {"simulated": True, "stop": True, "safety_symptom": {
            "id": symptom.pk, "text": label,
        }, "ranked_causes": [], "evidence": {"present": [], "absent": []},
                "next_question": None,
                "editable_symptoms": []}

    ranked = rank_causes(session, top=top, include_drafts=include_drafts)
    observed = evidence(session, include_drafts=include_drafts)
    visible_symptoms = _visible(Symptom.objects, include_drafts).filter(
        category=category)
    present_ids = set(observed["present"])
    absent_ids = set(observed["absent"])
    serialized = []
    for result in ranked:
        cause = result["cause"]
        link_rows = []
        links = cause.links.filter(
            symptom_id__in=present_ids | absent_ids,
            symptom__category_id=category.pk,
        ).select_related("symptom")
        for link in links:
            present = link.symptom_id in present_ids
            link_rows.append({
                "symptom_id": link.symptom_id,
                "symptom": (link.symptom.text_roman or link.symptom.text_en)
                if user.language == "roman_ur" else link.symptom.text_en,
                "strength": link.strength,
                "weight": float(link.weight),
                "contribution": "supports" if present else "contradicts",
            })
        serialized.append({
            "cause": {"id": cause.pk, "name": cause.name,
                      "system": cause.system, "severity": cause.severity,
                      "status": cause.status, "created_by": cause.created_by_id},
            "rank": result["rank"],
            "confidence": float(result["confidence"]),
            "explanation": result["explanation"],
            "supporting_symptoms": result["supporting_symptoms"],
            "contradicting_symptoms": result["contradicting_symptoms"],
            "contributing_links": link_rows,
            "all_links": [{"id": link.pk, "symptom_id": link.symptom_id,
                           "strength": link.strength}
                          for link in cause.links.filter(
                              symptom__in=visible_symptoms)],
        })
    question = next_question(session, ranked[:3], include_drafts=include_drafts)
    return {
        "simulated": True,
        "ranked_causes": serialized,
        "evidence": {
            "present": [{"id": pk,
                         "symptom": (item["symptom"].text_roman or item["symptom"].text_en)
                         if user.language == "roman_ur" else item["symptom"].text_en,
                         "answer": item["wording"]}
                        for pk, item in observed["present"].items()],
            "absent": [{"id": pk,
                        "symptom": (item["symptom"].text_roman or item["symptom"].text_en)
                        if user.language == "roman_ur" else item["symptom"].text_en,
                        "answer": item["wording"]}
                       for pk, item in observed["absent"].items()],
        },
        "next_question": _localized_question(question, user) if question else None,
        "editable_symptoms": [{"id": symptom.pk, "key": symptom.key,
                               "text": symptom.text_roman or symptom.text_en
                               if user.language == "roman_ur" else symptom.text_en}
                              for symptom in visible_symptoms],
    }
