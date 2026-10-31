"""Shared launch readiness checks for operators and reviewers."""
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from accounts.models import MechanicProfile
from knowledge.models import (AnswerOption, Cause, CauseSymptomLink, ContentReview,
                              Question, RepairCost, SelfCheck, Status, Symptom,
                              SymptomCategory, WarningLight)


def _item(obj):
    return {"id": obj.pk, "label": str(obj), "type": obj.__class__.__name__}


def _check(offenders):
    offenders = list(offenders)
    return {"passed": not offenders, "offenders": offenders}


def run_launch_checks(*, production=False, min_flows=None):
    """Return JSON-safe named checks, shared by the command and reviewer API."""
    minimum = min_flows if min_flows is not None else getattr(settings, "LAUNCH_MIN_FLOWS", 3)
    categories = list(SymptomCategory.objects.all())
    qualifying = []
    category_offenders = []
    for category in categories:
        symptoms = Symptom.objects.filter(category=category, status=Status.PUBLISHED,
                                          is_dummy=False)
        questions = Question.objects.filter(symptom__in=symptoms, status=Status.PUBLISHED,
                                            is_dummy=False)
        causes = Cause.objects.filter(links__symptom__in=symptoms, status=Status.PUBLISHED,
                                      is_dummy=False).distinct()
        links = CauseSymptomLink.objects.filter(cause__in=causes, symptom__in=symptoms)
        if symptoms.exists() and questions.exists() and causes.exists() and links.exists():
            qualifying.append(category)
        else:
            category_offenders.append({"id": category.pk, "label": category.name_en,
                                       "type": "SymptomCategory"})
    category_check = _check(category_offenders)
    count_check = _check([] if len(qualifying) >= minimum else [{"count": len(qualifying),
                         "minimum": minimum, "type": "PublishedFlowCount"}])

    # Anything attached to a published symptom can still be served via legacy
    # relations, so inspect all of its connected content including drafts.
    reachable_symptoms = Symptom.objects.filter(category__in=categories,
                                                status=Status.PUBLISHED)
    reachable_causes = Cause.objects.filter(links__symptom__in=reachable_symptoms).distinct()
    reachable_questions = Question.objects.filter(symptom__in=reachable_symptoms)
    reachable_checks = SelfCheck.objects.filter(cause__in=reachable_causes)
    reachable_costs = RepairCost.objects.filter(cause__in=reachable_causes)
    reachable_lights = WarningLight.objects.none()  # no flow relation exists for warning lights
    unsafe = []
    for model, queryset in ((Symptom, reachable_symptoms), (Cause, reachable_causes),
                            (Question, reachable_questions), (SelfCheck, reachable_checks),
                            (RepairCost, reachable_costs), (WarningLight, reachable_lights)):
        unsafe.extend(_item(obj) for obj in queryset.filter(is_dummy=True))
        if model is not WarningLight:
            unsafe.extend(_item(obj) for obj in queryset.filter(status__in=[Status.AI_DRAFT, Status.DRAFT]))

    safety_offenders = []
    for symptom in Symptom.objects.filter(is_safety_critical=True):
        ct = ContentType.objects.get_for_model(Symptom)
        approvals = ContentReview.objects.filter(content_type=ct, object_id=symptom.pk,
                         status=ContentReview.Decision.APPROVED).select_related("reviewed_by")
        valid = False
        for approval in approvals:
            reviewer = approval.reviewed_by
            if not reviewer:
                continue
            if reviewer.role == "admin" or reviewer.is_superuser:
                valid = True
            elif reviewer.role == "mechanic" and MechanicProfile.objects.filter(
                    user=reviewer, is_verified=True).exists():
                valid = True
        if symptom.status != Status.PUBLISHED or not valid:
            safety_offenders.append(_item(symptom))

    cutoff = timezone.localdate() - timedelta(days=120)
    stale_costs = [_item(cost) for cost in RepairCost.objects.filter(status=Status.PUBLISHED)
                   if cost.last_verified is None or cost.last_verified < cutoff]
    malformed_questions = []
    for question in Question.objects.filter(status=Status.PUBLISHED):
        options = list(question.options.all())
        if len(options) < 2 or sum(option.is_unsure for option in options) != 1:
            malformed_questions.append(_item(question))
    deficient_causes = []
    for cause in Cause.objects.filter(status=Status.PUBLISHED):
        if not cause.links.exists() or not cause.costs.exists():
            deficient_causes.append(_item(cause))

    settings_offenders = []
    if production:
        if settings.DEBUG:
            settings_offenders.append({"setting": "DEBUG", "value": True})
        if settings.ALLOW_DRAFT_CONTENT:
            settings_offenders.append({"setting": "ALLOW_DRAFT_CONTENT", "value": True})
        secret = getattr(settings._wrapped, "SECRET_KEY", "")
        if not secret or secret in {"django-insecure-change-me", "changeme", "replace-with-a-long-random-secret"}:
            settings_offenders.append({"setting": "SECRET_KEY", "value": "default or empty"})
        if not settings.ALLOWED_HOSTS:
            settings_offenders.append({"setting": "ALLOWED_HOSTS", "value": []})

    return {
        "categories_have_published_flows": category_check,
        "minimum_published_flows": count_check,
        "no_reachable_draft_or_dummy_content": _check(unsafe),
        "safety_critical_symptoms_approved": _check(safety_offenders),
        "published_costs_recent": _check(stale_costs),
        "questions_and_causes_complete": _check(malformed_questions + deficient_causes),
        "production_settings_sane": _check(settings_offenders),
    }
