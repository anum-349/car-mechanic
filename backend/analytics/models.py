from django.conf import settings
from django.db import models


class Event(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="analytics_events")
    session = models.ForeignKey("diagnosis.DiagnosisSession", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="analytics_events")
    name = models.CharField(max_length=40)
    props = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["name", "created_at"], name="analytics_name_created_idx")]


class DailyStat(models.Model):
    date = models.DateField()
    metric = models.CharField(max_length=80)
    dimension = models.CharField(max_length=120, blank=True, default="")
    value = models.DecimalField(max_digits=14, decimal_places=4)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["date", "metric", "dimension"],
                                                name="analytics_daily_stat_unique")]
        indexes = [models.Index(fields=["date", "metric"], name="analytics_stat_date_metric_idx")]
