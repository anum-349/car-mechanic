from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task(name="analytics.tasks.rollup_daily_stats")
def rollup_daily_stats():
    from .services import rollup_day

    return rollup_day(timezone.localdate() - timedelta(days=1))
