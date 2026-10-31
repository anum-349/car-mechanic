from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ScamCheck(models.Model):
    class Verdict(models.TextChoices):
        PLAUSIBLE = "plausible", "Plausible"
        DOUBTFUL = "doubtful", "Doubtful"
        SUSPICIOUS = "suspicious", "Suspicious"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="scam_checks")

    session = models.ForeignKey(
        "diagnosis.DiagnosisSession", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="scam_checks")
    claimed_cause = models.ForeignKey(
        "knowledge.Cause", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+")
    claim_text = models.CharField(max_length=300)
    quoted_price = models.PositiveIntegerField()  # PKR
    plausibility = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)])
    verdict = models.CharField(
        max_length=20, choices=Verdict.choices, default=Verdict.DOUBTFUL)
    city = models.CharField(max_length=60, blank=True)
    price_basis = models.CharField(max_length=20, default="unavailable")
    cost = models.JSONField(default=dict, blank=True)
    reasons = models.JSONField(default=list, blank=True)
    proof_suggestions = models.JSONField(default=list, blank=True)
    candidate_causes = models.JSONField(default=list, blank=True)
    limited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Scam check {self.pk}"
