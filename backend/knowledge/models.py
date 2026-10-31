from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models


STRENGTH_WEIGHT = {
    "always": Decimal("0.90"),
    "often": Decimal("0.70"),
    "sometimes": Decimal("0.40"),
    "rarely": Decimal("0.10"),
}


class GovernedQuerySet(models.QuerySet):
    def visible(self):
        from django.conf import settings

        if settings.ALLOW_DRAFT_CONTENT:
            return self.all()
        return self.filter(status=Status.PUBLISHED, is_dummy=False)


class GovernedManager(models.Manager.from_queryset(GovernedQuerySet)):
    pass


class Status(models.TextChoices):
    AI_DRAFT = "ai_draft", "AI draft"
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under review"
    APPROVED = "approved", "Approved"
    PUBLISHED = "published", "Published"
    REJECTED = "rejected", "Rejected"


class Governed(models.Model):
    """Shared workflow fields for all knowledge content."""
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    is_dummy = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = GovernedManager()

    class Meta:
        abstract = True


class SymptomCategory(models.Model):
    name_en = models.CharField(max_length=80)
    name_roman = models.CharField(max_length=80, blank=True)
    name_ur = models.CharField(max_length=80, blank=True)

    class Meta:
        verbose_name_plural = "symptom categories"

    def __str__(self):
        return self.name_en


class Symptom(Governed):
    key = models.SlugField(max_length=80, null=True, blank=True)
    category = models.ForeignKey(
        SymptomCategory, on_delete=models.CASCADE, related_name="symptoms"
    )
    text_en = models.CharField(max_length=200)
    text_roman = models.CharField(max_length=200, blank=True)
    text_ur = models.CharField(max_length=200, blank=True)
    is_safety_critical = models.BooleanField(default=False)
    is_observable = models.BooleanField(default=True)
    is_generic = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "key"], condition=models.Q(key__isnull=False),
                name="unique_symptom_key_per_category",
            ),
        ]

    def __str__(self):
        return self.text_en


class Cause(Governed):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    name = models.CharField(max_length=150)
    system = models.CharField(max_length=60)  # electrical, cooling, fuel...
    description = models.TextField(blank=True)
    proof_hint = models.TextField(blank=True)
    prior = models.DecimalField(
        max_digits=4, decimal_places=3, default=Decimal("0.100"),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    severity = models.CharField(
        max_length=10, choices=Severity.choices, default=Severity.MEDIUM
    )
    safe_to_drive = models.BooleanField(default=True)
    car_models = models.ManyToManyField(
        "garage.CarModel", blank=True, related_name="causes"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(prior__gte=0) & models.Q(prior__lte=1),
                name="cause_prior_between_zero_one",
            ),
        ]

    def __str__(self):
        return self.name


class CauseSymptomLink(models.Model):
    class Strength(models.TextChoices):
        ALWAYS = "always", "Always"
        OFTEN = "often", "Often"
        SOMETIMES = "sometimes", "Sometimes"
        RARELY = "rarely", "Rarely"

    cause = models.ForeignKey(Cause, on_delete=models.CASCADE, related_name="links")
    symptom = models.ForeignKey(Symptom, on_delete=models.CASCADE, related_name="links")
    strength = models.CharField(max_length=10, choices=Strength.choices)
    weight = models.DecimalField(max_digits=3, decimal_places=2, editable=False)
    car_model = models.ForeignKey(
        "garage.CarModel", null=True, blank=True, on_delete=models.CASCADE,
        related_name="cause_symptom_links",
    )

    class Meta:
        indexes = [models.Index(fields=["cause", "symptom"]) ]
        constraints = [
            models.UniqueConstraint(
                fields=["cause", "symptom", "car_model"],
                condition=models.Q(car_model__isnull=False),
                name="unique_cause_symptom_model",
            ),
            models.UniqueConstraint(
                fields=["cause", "symptom"],
                condition=models.Q(car_model__isnull=True),
                name="unique_cause_symptom_generic",
            ),
        ]

    def save(self, *args, **kwargs):
        self.weight = STRENGTH_WEIGHT[self.strength]
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"weight"}
        super().save(*args, **kwargs)


class Question(Governed):
    class QType(models.TextChoices):
        SINGLE = "single_choice", "Single choice"
        YES_NO = "yes_no", "Yes / No"
        MEDIA = "media_choice", "Media choice"

    symptom = models.ForeignKey(
        Symptom, on_delete=models.CASCADE, related_name="questions"
    )
    text_en = models.CharField(max_length=250)
    text_roman = models.CharField(max_length=250, blank=True)
    text_ur = models.CharField(max_length=250, blank=True)
    type = models.CharField(max_length=20, choices=QType.choices, default=QType.SINGLE)
    media_url = models.CharField(max_length=300, blank=True)
    is_context = models.BooleanField(default=False)
    is_triage = models.BooleanField(default=False)
    triage_order = models.PositiveSmallIntegerField(default=0)
    requires_symptom = models.ForeignKey(Symptom, null=True, blank=True,
      on_delete=models.SET_NULL, related_name="follow_up_questions")

    @staticmethod
    def validate_option_data(options):
        if (not isinstance(options, (list, tuple)) or len(options) < 2
                or any(not isinstance(option, dict) for option in options)
                or sum(bool(option.get("is_unsure", False)) for option in options) != 1):
            raise ValidationError("A question needs at least two options and exactly one unsure option.")

    def validate_options(self, options=None):
        if options is None:
            options = list(self.options.all()) if self.pk else []
            options = [{"is_unsure": option.is_unsure} for option in options]
        self.validate_option_data(options)

    def clean(self):
        super().clean()
        if self.pk:
            self.validate_options()

    def __str__(self):
        return self.text_en

class AnswerEffect(models.TextChoices):
    CONFIRMS = "confirms", "Confirms the symptom"    # present evidence
    DENIES = "denies", "Denies the symptom"          # absent evidence
    CONTEXT = "context", "Context only"              # no symptom evidence
    UNSURE = "unsure", "Driver is unsure"            # no evidence


class ContextKey(models.TextChoices):
    WHEN = "when", "When it happens"
    FREQUENCY = "frequency", "How often"
    RECENT_EVENT = "recent_event", "Recent event"


CONTEXT_VALUES = {
    "when": {"idle", "braking", "accelerating", "uphill", "cold_start", "hot_engine",
             "turning", "highway", "rain", "ac_on"},
    "frequency": {"always", "often", "sometimes", "once"},
    "recent_event": {"refuelling", "repair", "accident", "battery_change", "warning_light"},
}

class AnswerOption(models.Model):
    question = models.ForeignKey("Question", on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=150)
    label_roman = models.CharField(max_length=150, blank=True)
    label_ur = models.CharField(max_length=150, blank=True)   # NEW: you had no Urdu option field
    is_unsure = models.BooleanField(default=False)            # kept; mirrors effect == unsure
    implies_symptom = models.ForeignKey("Symptom", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="+")
    effect = models.CharField(max_length=10, choices=AnswerEffect.choices,
                              default=AnswerEffect.UNSURE)   # unclassified => no evidence
    context_key = models.CharField(max_length=20, choices=ContextKey.choices, blank=True)
    context_value = models.CharField(max_length=40, blank=True)

    @property
    def label_en(self):
        return self.label

    def clean(self):
        super().clean()
        if self.context_key or self.context_value:
            if self.context_value not in CONTEXT_VALUES.get(self.context_key, set()):
                raise ValidationError("Unknown context key/value.")
            if self.effect in (AnswerEffect.UNSURE, AnswerEffect.DENIES):
                raise ValidationError("An unsure or denying option cannot carry context.")

    def save(self, *args, **kwargs):
        self.is_unsure = self.effect == AnswerEffect.UNSURE
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"is_unsure"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class SelfCheck(Governed):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    cause = models.ForeignKey(Cause, on_delete=models.CASCADE, related_name="self_checks")
    steps = models.TextField()
    tools_needed = models.CharField(max_length=150, blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)


class RepairCost(Governed):
    cause = models.ForeignKey(Cause, on_delete=models.CASCADE, related_name="costs")
    city = models.CharField(max_length=60)
    parts_min = models.PositiveIntegerField(default=0)
    parts_max = models.PositiveIntegerField(default=0)
    labour_min = models.PositiveIntegerField(default=0)
    labour_max = models.PositiveIntegerField(default=0)
    last_verified = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cause", "city"], name="unique_cost_per_cause_city"),
            models.CheckConstraint(condition=models.Q(parts_min__lte=models.F("parts_max")), name="parts_min_lte_parts_max"),
            models.CheckConstraint(condition=models.Q(labour_min__lte=models.F("labour_max")), name="labour_min_lte_labour_max"),
        ]


class WarningLight(models.Model):
    class Severity(models.TextChoices):
        STOP_NOW = "stop_now", "Stop now"
        REPAIR_SOON = "repair_soon", "Repair soon"
        INFO = "info", "Information"

    name = models.CharField(max_length=100, unique=True)
    icon_url = models.CharField(max_length=300, blank=True)
    severity = models.CharField(max_length=15, choices=Severity.choices)
    meaning = models.TextField()
    recommended_action = models.TextField()
    meaning_roman = models.TextField(blank=True)
    action_roman = models.TextField(blank=True)
    is_dummy = models.BooleanField(default=True)

    def __str__(self):
        return self.name



class ObdCode(models.Model):
    code = models.CharField(max_length=10, primary_key=True)
    description = models.CharField(max_length=250)
    system = models.CharField(max_length=60, blank=True)
    causes = models.ManyToManyField(Cause, through="ObdCodeCause", blank=True, related_name="obd_codes")

    def __str__(self):
        return self.code


class ObdCodeCause(models.Model):
    obd_code = models.ForeignKey(ObdCode, on_delete=models.CASCADE, db_column="obdcode_id", related_name="cause_links")
    cause = models.ForeignKey(Cause, on_delete=models.CASCADE, related_name="obd_code_links")

    class Meta:
        db_table = "knowledge_obdcode_causes"
        constraints = [models.UniqueConstraint(fields=["obd_code", "cause"], name="unique_obd_code_cause")]


class ContentReview(models.Model):
    """Approval history and version snapshots for any governed item."""
    class Decision(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        RETURNED = "returned", "Returned for changes"
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"
        REVISION_CREATED = "revision_created", "Revision created"
        CLAIMED = "claimed", "Claimed by mechanic"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Decision.choices)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    comment = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["content_type", "object_id"])]
        ordering = ["-created_at"]


class ContentRevision(models.Model):
    class RevisionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        RETURNED = "returned", "Returned"
        REJECTED = "rejected", "Rejected"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    base_version = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="content_revisions",
    )
    status = models.CharField(max_length=20, choices=RevisionStatus.choices,
                              default=RevisionStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["content_type", "object_id", "status"])]
        ordering = ["-created_at"]


CONTENT_REVIEW_DECISION_CHOICES = ContentReview.Decision.choices
CONTENT_REVISION_STATUS_CHOICES = ContentRevision.RevisionStatus.choices
