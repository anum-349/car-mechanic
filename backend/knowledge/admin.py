from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .importer import ImportErrorInFile, import_flow
from .models import (AnswerOption, Cause, CauseSymptomLink, ContentReview,
                     ObdCode, ObdCodeCause, Question, RepairCost, SelfCheck, Status,
                     Symptom, SymptomCategory, WarningLight)
from .services import workflow


class GovernedAdmin(admin.ModelAdmin):
    """Shared behaviour for content that goes through review."""
    list_filter = ["status", "is_dummy"]
    readonly_fields = ["created_by", "approved_by", "created_at", "updated_at",
                       "status", "version", "is_dummy"]
    actions = ["submit_for_review", "approve", "publish"]

    def sample_marker(self, obj):
        if obj.is_dummy:
            return mark_safe(
                '<strong style="background:#fff0a6;color:#6b4e00;padding:2px 6px">SAMPLE</strong>'
            )
        return ""

    sample_marker.short_description = "Sample"

    @staticmethod
    def _require_reviewer(request):
        if (not request.user.is_authenticated
                or (request.user.role not in {"reviewer", "admin"}
                    and not request.user.is_superuser)):
            raise PermissionDenied("Only reviewers and admins can change content status.")

    def save_model(self, request, obj, form, change):
        if isinstance(obj, (SelfCheck, RepairCost)) and obj.cause.status in {
                Status.APPROVED, Status.PUBLISHED}:
            raise ValidationError(
                "Self-checks and costs on approved causes must be changed in a cause revision.")
        if change:
            original = self.model.objects.get(pk=obj.pk)
            if original.status in {Status.APPROVED, Status.PUBLISHED}:
                raise ValidationError(
                    "Approved content must be changed through a reviewed content revision.")
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if obj.status in {Status.APPROVED, Status.PUBLISHED}:
            raise ValidationError("Approved content cannot be deleted.")
        if isinstance(obj, (SelfCheck, RepairCost)) and obj.cause.status in {
                Status.APPROVED, Status.PUBLISHED}:
            raise ValidationError(
                "Self-checks and costs on approved causes must be changed in a cause revision.")
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset.select_related("cause") if queryset.model in {
                SelfCheck, RepairCost} else queryset:
            if obj.status in {Status.APPROVED, Status.PUBLISHED}:
                raise ValidationError("Approved content cannot be deleted.")
            if isinstance(obj, (SelfCheck, RepairCost)) and obj.cause.status in {
                    Status.APPROVED, Status.PUBLISHED}:
                raise ValidationError(
                    "Self-checks and costs on approved causes must be changed in a cause revision.")
        super().delete_queryset(request, queryset)

    @admin.action(description="Mark as submitted")
    def submit_for_review(self, request, queryset):
        self._require_reviewer(request)
        for obj in queryset:
            try:
                workflow.submit(obj, request.user)
            except workflow.WorkflowError as exc:
                self.message_user(request, str(exc), messages.ERROR)

    @admin.action(description="Approve")
    @transaction.atomic
    def approve(self, request, queryset):
        self._require_reviewer(request)
        for obj in queryset:
            try:
                workflow.approve(obj, request.user)
            except workflow.WorkflowError as exc:
                self.message_user(request, str(exc), messages.ERROR)
            except PermissionDenied as exc:
                self.message_user(request, str(exc), messages.ERROR)

    @admin.action(description="Publish approved")
    def publish(self, request, queryset):
        self._require_reviewer(request)
        for obj in queryset:
            try:
                workflow.publish(obj, request.user)
            except workflow.WorkflowError as exc:
                self.message_user(request, str(exc), messages.ERROR)

    def save_formset(self, request, form, formset, change):
        obj = form.instance
        if obj.pk and obj.status in {Status.APPROVED, Status.PUBLISHED}:
            raise ValidationError(
                "Approved content must be changed through a reviewed content revision.")
        super().save_formset(request, form, formset, change)


@admin.register(SymptomCategory)
class SymptomCategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name_en", "name_roman"]
    search_fields = ["name_en", "name_roman"]
    change_list_template = "admin/knowledge/symptomcategory_change_list.html"

    def get_urls(self):
        return [path("import-json/",
                     self.admin_site.admin_view(self.import_json_view),
                     name="knowledge_import_json")] + super().get_urls()

    def import_json_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            upload = request.FILES.get("file")
            if upload and (upload.size > 2_000_000 or
                           not upload.name.lower().endswith(".json") or
                           upload.content_type not in {"application/json", "text/json"}):
                messages.error(request, "Upload a JSON file no larger than 2 MB.")
                raw = None
            else:
                raw = upload.read().decode("utf-8-sig") if upload \
                    else request.POST.get("text", "")
                if len(raw.encode("utf-8")) > 2_000_000:
                    messages.error(request, "JSON input must be no larger than 2 MB.")
                    raw = None
            try:
                if raw is None:
                    raise ImportErrorInFile(["Upload exceeds the accepted file policy."])
                counts = import_flow(raw, user=request.user)
            except ImportErrorInFile as e:
                messages.error(request, f"Import failed, nothing saved: {e}")
            except Exception as e:  # unexpected data problems
                messages.error(request, f"Import failed, nothing saved: {e!r}")
            else:
                messages.success(request, f"Imported: {counts}")
                return redirect("..")
        context = {**self.admin_site.each_context(request),
                   "title": "Import diagnostic flow (JSON)",
                   "opts": self.model._meta}
        return TemplateResponse(request, "admin/knowledge/import_json.html",
                                context)


@admin.register(Symptom)
class SymptomAdmin(GovernedAdmin):
    list_display = ["id", "text_en", "category", "is_safety_critical",
                    "status", "is_dummy", "sample_marker", "version"]
    list_filter = GovernedAdmin.list_filter + ["category", "is_safety_critical"]
    search_fields = ["text_en", "text_roman"]
    autocomplete_fields = ["category"]


class CauseSymptomLinkInline(admin.TabularInline):
    model = CauseSymptomLink
    extra = 1
    autocomplete_fields = ["symptom"]
    readonly_fields = ["weight", "derived_label"]

    @admin.display(description="Derived strength weight")
    def derived_label(self, obj):
        if not obj.pk:
            return "Set by strength"
        return f"{obj.get_strength_display()} → {obj.weight}"


class SelfCheckInline(admin.TabularInline):
    model = SelfCheck
    extra = 0
    fields = ["steps", "tools_needed", "difficulty", "status", "is_dummy"]


class RepairCostInline(admin.TabularInline):
    model = RepairCost
    extra = 0
    fields = ["city", "parts_min", "parts_max", "labour_min", "labour_max",
              "last_verified", "source", "status", "is_dummy"]


@admin.register(Cause)
class CauseAdmin(GovernedAdmin):
    list_display = ["id", "name", "system", "severity", "safe_to_drive",
                    "prior", "status", "is_dummy", "sample_marker", "version"]
    list_filter = GovernedAdmin.list_filter + ["system", "severity",
                                               "safe_to_drive"]
    search_fields = ["name", "system", "description"]
    filter_horizontal = ["car_models"]
    inlines = [CauseSymptomLinkInline, SelfCheckInline, RepairCostInline]


@admin.register(CauseSymptomLink)
class CauseSymptomLinkAdmin(admin.ModelAdmin):
    list_display = ["id", "cause", "symptom", "strength", "weight_label"]
    list_filter = ["strength"]
    search_fields = ["cause__name", "symptom__text_en"]
    autocomplete_fields = ["cause", "symptom"]
    readonly_fields = ["weight"]

    @staticmethod
    def _check_parent(obj):
        if obj.cause_id and obj.cause.status in {Status.APPROVED, Status.PUBLISHED}:
            raise ValidationError(
                "Links on approved content must be changed in a cause revision.")

    def save_model(self, request, obj, form, change):
        self._check_parent(obj)
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        self._check_parent(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset.select_related("cause"):
            self._check_parent(obj)
        super().delete_queryset(request, queryset)

    @admin.display(description="Derived weight")
    def weight_label(self, obj):
        return f"{obj.get_strength_display()} → {obj.weight}"


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 2
    autocomplete_fields = ["implies_symptom"]


@admin.register(Question)
class QuestionAdmin(GovernedAdmin):
    list_display = ["id", "text_en", "symptom", "type", "status", "is_dummy",
                    "sample_marker"]
    list_filter = GovernedAdmin.list_filter + ["type"]
    search_fields = ["text_en", "text_roman", "symptom__text_en"]
    autocomplete_fields = ["symptom"]
    inlines = [AnswerOptionInline]


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ["id", "label", "question", "is_unsure",
                    "implies_symptom"]
    list_filter = ["is_unsure"]
    search_fields = ["label", "label_roman", "question__text_en"]
    autocomplete_fields = ["question", "implies_symptom"]

    @staticmethod
    def _check_question(obj):
        if obj.question_id and obj.question.status in {Status.APPROVED, Status.PUBLISHED}:
            raise ValidationError(
                "Options on approved questions must be changed in a question revision.")

    def save_model(self, request, obj, form, change):
        self._check_question(obj)
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        self._check_question(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset.select_related("question"):
            self._check_question(obj)
        super().delete_queryset(request, queryset)


@admin.register(SelfCheck)
class SelfCheckAdmin(GovernedAdmin):
    list_display = ["id", "cause", "difficulty", "tools_needed", "status",
                    "is_dummy", "sample_marker", "version"]
    list_filter = GovernedAdmin.list_filter + ["difficulty"]
    search_fields = ["cause__name", "steps", "tools_needed"]
    autocomplete_fields = ["cause"]


@admin.register(RepairCost)
class RepairCostAdmin(GovernedAdmin):
    list_display = ["id", "cause", "city", "parts_min", "parts_max",
                    "labour_min", "labour_max", "last_verified", "status",
                    "is_dummy", "sample_marker", "version"]
    list_filter = GovernedAdmin.list_filter + ["city", "last_verified"]
    search_fields = ["cause__name", "city", "source"]
    autocomplete_fields = ["cause"]


@admin.register(WarningLight)
class WarningLightAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "severity"]
    list_filter = ["severity"]
    search_fields = ["name", "meaning"]


class ObdCodeCauseInline(admin.TabularInline):
    model = ObdCodeCause
    extra = 0
    autocomplete_fields = ["cause"]


@admin.register(ObdCode)
class ObdCodeAdmin(admin.ModelAdmin):
    list_display = ["code", "description", "system"]
    list_filter = ["system"]
    search_fields = ["code", "description"]
    inlines = [ObdCodeCauseInline]


@admin.register(ObdCodeCause)
class ObdCodeCauseAdmin(admin.ModelAdmin):
    list_display = ["id", "obd_code", "cause"]
    search_fields = ["obd_code__code", "cause__name"]
    autocomplete_fields = ["obd_code", "cause"]


@admin.register(ContentReview)
class ContentReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "content_type", "object_id", "version", "status",
                    "submitted_by", "reviewed_by", "created_at"]
    list_filter = ["status", "content_type"]
    search_fields = ["comment", "submitted_by__username",
                     "reviewed_by__username"]
    raw_id_fields = ["submitted_by", "reviewed_by"]
    readonly_fields = ["created_at", "reviewed_at"]
    date_hierarchy = "created_at"
