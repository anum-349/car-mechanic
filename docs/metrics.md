# Analytics metrics

All dashboard metrics use the trailing 30 local calendar dates, including today. Sessions are assigned to the date of `DiagnosisSession.started_at`. Ratios with a zero denominator are returned as `0`; denominator counts are exposed for top-three accuracy and cost-range hit rate. Category and question labels are knowledge-base labels, never user-entered text. `Event.props` accepts only the documented structured identifiers/enums; free text, phones, and exact locations are not recorded.

The ORM examples below assume `since = localdate() - 29 days` and `through = localdate()`.

| Metric | Definition and ORM logic |
| --- | --- |
| Sessions per day | Count all `DiagnosisSession` rows where `started_at__date` is between `since` and `through`, grouped by `TruncDate(started_at)`. Days with zero sessions are omitted. |
| Top categories | Count the same in-period sessions grouped by `category_id`; order descending by count and return at most ten. Categories with no sessions do not appear. |
| Question drop-off | `question_asked` is an internal server event emitted when a distinct session/question is returned to a user. For every exposure, count `answered` when a `SessionAnswer(session_id, question_id)` exists. Count `asked_then_abandoned` only when no such answer exists and the session status is `abandoned`. In-progress unanswered exposures remain in `asked` but neither outcome bucket. Repeated page loads do not create a second exposure for the same session/question. |
| Average questions per session | Average the number of `SessionAnswer` rows per `completed` session in the period. Completed sessions with zero answers count as zero; unfinished sessions are excluded. |
| Share rate | Distinct completed session IDs with at least one `share_clicked` event divided by the number of completed sessions in period. The numerator is bounded to in-period completed sessions. |
| Outcome rate | Distinct in-period completed session IDs with an `Outcome` row divided by in-period completed sessions. |
| Top-three accuracy | Among in-period `Outcome` rows with a non-null `actual_cause`, proportion where any `SessionResult` for that session has the same cause and `rank <= 3`. Outcomes recorded as unmatched free text are excluded. |
| Cost-range hit rate | Among in-period outcomes with non-null `actual_cost`, proportion whose cost falls inclusively within at least one server-snapshotted cost range in that session's `result_viewed` event. The snapshot stores only cause IDs and numeric PKR bounds. Outcomes for which no range was shown are excluded; the denominator is returned. |
| Safety-stop count | Number of in-period sessions with `safety_alert=True`, assigned by session start date. |

## Representative ORM/SQL

The dashboard implementation is in `backend/analytics/services.py`. Equivalent query shapes:

```python
DiagnosisSession.objects.filter(
    started_at__date__range=(since, through)
).annotate(day=TruncDate("started_at")).values("day").annotate(
    value=Count("id")
)

DiagnosisSession.objects.filter(
    started_at__date__range=(since, through)
).values("category_id").annotate(value=Count("id"))

SessionAnswer.objects.filter(
    session__status="completed",
    session__started_at__date__range=(since, through),
).values("session_id").annotate(question_count=Count("id")).aggregate(
    average=Avg("question_count")
)
```

Raw events are retained in the first-party event table for metric attribution. The Celery beat job runs daily at 02:15 and writes/replaces previous-local-day `DailyStat` counts for sessions, safety stops, category session counts, shares, outcomes, and scam checks. The reviewer API calculates the richer rolling ratios directly from source rows so it can include their explicit denominators.
