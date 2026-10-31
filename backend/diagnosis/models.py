from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class DiagnosisSession(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="diagnosis_sessions")
    car = models.ForeignKey(
        "garage.Car", on_delete=models.CASCADE,
        related_name="diagnosis_sessions")
    category = models.ForeignKey(
        "knowledge.SymptomCategory", on_delete=models.PROTECT,
        null=True, blank=True)
    diagnosis_type = models.CharField(
        max_length=10, choices=[("text", "Text"), ("obd", "OBD")],
        default="text")
    obd_code = models.ForeignKey(
        "knowledge.ObdCode", on_delete=models.PROTECT,
        null=True, blank=True, related_name="diagnosis_sessions")
    mechanic_reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="mechanic_reported_sessions")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    safety_alert = models.BooleanField(default=False)
    free_text = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Diagnosis session {self.pk}"


class SessionAnswer(models.Model):
    session = models.ForeignKey(
        DiagnosisSession, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(
        "knowledge.Question", on_delete=models.PROTECT)
    option = models.ForeignKey(
        "knowledge.AnswerOption", on_delete=models.PROTECT)
    free_text = models.CharField(max_length=300, blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["session", "question"],
            name="one_answer_per_question")]

    def __str__(self):
        return f"Answer to {self.question_id} in session {self.session_id}"


class SessionSymptom(models.Model):
    class Source(models.TextChoices):
        FREE_TEXT = "free_text", "Free text"

    session = models.ForeignKey(
        DiagnosisSession, on_delete=models.CASCADE, related_name="session_symptoms")
    symptom = models.ForeignKey("knowledge.Symptom", on_delete=models.PROTECT,
                                related_name="session_symptoms")
    source = models.CharField(max_length=20, choices=Source.choices,
                              default=Source.FREE_TEXT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["session", "symptom", "source"],
            name="unique_session_symptom_source")]

    def __str__(self):
        return f"{self.symptom_id} in session {self.session_id} ({self.source})"


class SessionResult(models.Model):
    session = models.ForeignKey(
        DiagnosisSession, on_delete=models.CASCADE, related_name="results")
    cause = models.ForeignKey("knowledge.Cause", on_delete=models.PROTECT)
    cause_name = models.CharField(max_length=150)
    rank = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    confidence = models.DecimalField(
        max_digits=4, decimal_places=3, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)])
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ["rank"]
        constraints = [models.UniqueConstraint(
            fields=["session", "rank"], name="unique_rank_per_session")]

    def save(self, *args, **kwargs):
        if not self.cause_name and self.cause_id:
            self.cause_name = self.cause.name
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"cause_name"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Rank {self.rank}: {self.cause_name}"

class SessionContextFact(models.Model):
    class Source(models.TextChoices):
        ANSWER = "answer", "Answer"
        FREE_TEXT = "free_text", "Free text"

    session = models.ForeignKey("diagnosis.DiagnosisSession", on_delete=models.CASCADE,
                                related_name="context_facts")
    key = models.CharField(max_length=20)
    value = models.CharField(max_length=40)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ANSWER)
    answer = models.ForeignKey("diagnosis.SessionAnswer", null=True, blank=True,
                               on_delete=models.CASCADE, related_name="context_facts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["session", "key", "value"], name="unique_context_fact")]

class Outcome(models.Model):
    session = models.OneToOneField(
        DiagnosisSession, on_delete=models.CASCADE, related_name="outcome")
    actual_cause = models.ForeignKey(
        "knowledge.Cause", null=True, blank=True, on_delete=models.PROTECT)
    actual_cause_text = models.CharField(max_length=200, blank=True)
    actual_cost = models.PositiveIntegerField(null=True, blank=True)  # PKR
    mechanic = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+")
    mechanic_type = models.CharField(max_length=120, blank=True)
    was_helpful = models.BooleanField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Outcome for session {self.session_id}"


class MechanicRepairOutcome(models.Model):
    class RepairStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    class ResultStatus(models.TextChoices):
        RESOLVED = "resolved", "Resolved"
        PARTIALLY_RESOLVED = "partially_resolved", "Partially resolved"
        NOT_RESOLVED = "not_resolved", "Not resolved"
        UNABLE_TO_VERIFY = "unable_to_verify", "Unable to verify"
        FURTHER_DIAGNOSIS = "further_diagnosis", "Further diagnosis required"

    session = models.OneToOneField(
        DiagnosisSession, on_delete=models.CASCADE, related_name="mechanic_outcome")
    mechanic = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="repair_outcomes")
    actual_cause = models.ForeignKey(
        "knowledge.Cause", null=True, blank=True, on_delete=models.PROTECT)
    actual_cause_text = models.CharField(max_length=200, blank=True)
    actual_cost = models.PositiveIntegerField(null=True, blank=True)
    repair_status = models.CharField(
        max_length=20, choices=RepairStatus.choices, blank=True)
    result_status = models.CharField(
        max_length=24, choices=ResultStatus.choices, blank=True)
    repair_actions = models.TextField(blank=True)
    parts_replaced = models.TextField(blank=True)
    follow_up_notes = models.TextField(blank=True)
    parts_cost = models.PositiveIntegerField(null=True, blank=True)
    labor_cost = models.PositiveIntegerField(null=True, blank=True)
    other_cost = models.PositiveIntegerField(null=True, blank=True)
    repaired_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Mechanic repair outcome for session {self.session_id}"


class MechanicInspection(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    session = models.ForeignKey(
        DiagnosisSession, on_delete=models.CASCADE, related_name="mechanic_inspections")
    mechanic = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="diagnosis_inspections")
    inspection_date = models.DateField(null=True, blank=True)
    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    findings = models.TextField(blank=True)
    tests_performed = models.TextField(blank=True)
    tools_used = models.TextField(blank=True)
    additional_obd_codes = models.JSONField(default=list, blank=True)
    suspected_cause = models.ForeignKey(
        "knowledge.Cause", null=True, blank=True, on_delete=models.PROTECT)
    suspected_cause_text = models.CharField(max_length=200, blank=True)
    safety_concerns = models.TextField(blank=True)
    further_testing_required = models.BooleanField(default=False)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class MechanicOutcomeAudit(models.Model):
    outcome = models.ForeignKey(
        MechanicRepairOutcome, on_delete=models.CASCADE, related_name="audit_entries")
    mechanic = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="diagnosis_outcome_audits")
    action = models.CharField(max_length=24)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notifications")
    kind = models.CharField(max_length=60)
    payload = models.JSONField(default=dict)
    dedupe_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "created_at"])]


DIAGNOSIS_SESSION_STATUS_CHOICES = DiagnosisSession.Status.choices
