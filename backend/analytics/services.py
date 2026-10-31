from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from diagnosis.models import DiagnosisSession, Outcome, SessionAnswer
from knowledge.models import ContentReview, Question, Symptom

from .models import Event


def emit(name, *, user=None, user_id=None, session=None, props=None):
    """Record only structured, privacy-safe server-generated properties."""
    values = {"session": session, "name": name, "props": props or {}}
    if user is not None:
        values["user"] = user
    elif user_id is not None:
        values["user_id"] = user_id
    return Event.objects.create(**values)


def track_question_asked(session, question):
    props = {"question_id": question.pk}
    if not Event.objects.filter(name="question_asked", session=session, props=props).exists():
        emit("question_asked", user_id=session.user_id, session=session, props=props)


def record_result_viewed(session, user, cost_ranges):
    event = Event.objects.filter(name="result_viewed", session=session).first()
    if event is None:
        return emit("result_viewed", user=user, session=session,
                    props={"cost_ranges": cost_ranges})
    if "cost_ranges" not in event.props:
        event.props = {**event.props, "cost_ranges": cost_ranges}
        event.save(update_fields=["props"])
    return event


def _series(queryset, date_field, label="day"):
    return list(queryset.annotate(day=TruncDate(date_field)).values(label).annotate(
        value=Count("id")).order_by(label))


def analytics_snapshot(*, days=30):
    today = timezone.localdate()
    since = today - timedelta(days=days - 1)
    sessions = DiagnosisSession.objects.filter(started_at__date__gte=since,
                                                started_at__date__lte=today)
    completed = sessions.filter(status=DiagnosisSession.Status.COMPLETED)
    outcomes = Outcome.objects.filter(session__in=sessions)
    answered = SessionAnswer.objects.filter(session__in=sessions)

    sessions_by_day = _series(sessions, "started_at")
    category_rows = list(sessions.values("category_id", "category__name_en").annotate(
        value=Count("id")).order_by("-value", "category__name_en")[:10])
    question_events = Event.objects.filter(name="question_asked", created_at__date__gte=since,
                                           created_at__date__lte=today,
                                           session__in=sessions).values_list("session_id", "props")
    dropoff = {}
    for session_id, props in question_events:
        question_id = str(props.get("question_id", "unknown"))
        bucket = dropoff.setdefault(question_id, {"asked": 0, "answered": 0,
                                                   "asked_then_abandoned": 0})
        bucket["asked"] += 1
        has_answer = answered.filter(session_id=session_id,
                                     question_id=props.get("question_id")).exists()
        if has_answer:
            bucket["answered"] += 1
        elif sessions.filter(pk=session_id, status=DiagnosisSession.Status.ABANDONED).exists():
            bucket["asked_then_abandoned"] += 1
    question_names = dict(Question.objects.filter(pk__in=dropoff.keys()).values_list("pk", "text_en"))
    dropoff_rows = [{"question_id": int(key) if key.isdigit() else None,
                     "question": question_names.get(int(key), "Unknown question") if key.isdigit() else "Unknown question",
                     **value} for key, value in dropoff.items()]

    result_events = Event.objects.filter(name="result_viewed", session__in=sessions)
    shares = Event.objects.filter(name="share_clicked", session__in=completed).values(
        "session_id").distinct().count()
    outcome_count = outcomes.values("session_id").distinct().count()
    outcome_causes = outcomes.filter(actual_cause__isnull=False)
    top3_total = outcome_causes.count()
    top3_hits = sum(outcome.session.results.filter(rank__lte=3,
                                                   cause=outcome.actual_cause).exists()
                    for outcome in outcome_causes.select_related("session", "actual_cause"))
    cost_total = 0
    cost_hits = 0
    for outcome in outcomes.filter(actual_cost__isnull=False).select_related("session"):
        snapshots = result_events.filter(session=outcome.session).values_list("props", flat=True)
        ranges = [cost_range for props in snapshots for cost_range in props.get("cost_ranges", [])]
        if ranges:
            cost_total += 1
            if any(item.get("min", 0) <= outcome.actual_cost <= item.get("max", -1)
                   for item in ranges):
                cost_hits += 1
    safety_count = sessions.filter(safety_alert=True).count()

    average_questions = completed.annotate(question_count=Count("answers")).aggregate(
        value=Avg("question_count"))["value"] or 0
    return {
        "period_days": days,
        "sessions_per_day": sessions_by_day,
        "top_categories": [{"category_id": row["category_id"],
                            "category": row["category__name_en"], "sessions": row["value"]}
                           for row in category_rows],
        "question_dropoff": sorted(dropoff_rows, key=lambda row: (-row["asked"], row["question_id"] or 0)),
        "average_questions_per_session": average_questions,
        "share_rate": shares / completed.count() if completed.exists() else 0,
        "outcome_rate": outcome_count / completed.count() if completed.exists() else 0,
        "top3_accuracy": top3_hits / top3_total if top3_total else 0,
        "top3_denominator": top3_total,
        "cost_range_hit_rate": cost_hits / cost_total if cost_total else 0,
        "cost_range_denominator": cost_total,
        "safety_stop_count": safety_count,
    }


def rollup_day(day):
    from .models import DailyStat

    sessions = DiagnosisSession.objects.filter(started_at__date=day)
    rows = [DailyStat(date=day, metric="sessions", value=sessions.count()),
            DailyStat(date=day, metric="safety_stops", value=sessions.filter(safety_alert=True).count())]
    rows.extend(DailyStat(date=day, metric="sessions_by_category", dimension=str(item["category_id"]),
                          value=item["total"]) for item in sessions.values("category_id").annotate(
                              total=Count("id")))
    from scamshield.models import ScamCheck

    rows.append(DailyStat(date=day, metric="outcomes",
                          value=Outcome.objects.filter(created_at__date=day).count()))
    rows.append(DailyStat(date=day, metric="scam_checks",
                          value=ScamCheck.objects.filter(created_at__date=day).count()))
    for metric, event_name in (("shares", "share_clicked"),):
        rows.append(DailyStat(date=day, metric=metric,
                              value=Event.objects.filter(name=event_name,
                                                        created_at__date=day).count()))
    with transaction.atomic():
        DailyStat.objects.filter(date=day).delete()
        DailyStat.objects.bulk_create(rows)
    return len(rows)
