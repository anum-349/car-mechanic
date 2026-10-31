from django.contrib import admin
from django.utils import timezone

from .models import DiagnosisSession, Notification, Outcome, SessionAnswer, SessionResult


class SessionAnswerInline(admin.TabularInline):
    model = SessionAnswer
    extra = 0
    raw_id_fields = ["question", "option"]
    readonly_fields = ["answered_at"]


class SessionResultInline(admin.TabularInline):
    model = SessionResult
    extra = 0
    raw_id_fields = ["cause"]


@admin.register(DiagnosisSession)
class DiagnosisSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "car", "category", "status",
                    "safety_alert", "started_at", "completed_at"]
    list_filter = ["status", "safety_alert", "category", "started_at"]
    search_fields = ["user__username", "user__email", "car__nickname",
                     "free_text"]
    raw_id_fields = ["user", "car"]
    readonly_fields = ["started_at"]
    date_hierarchy = "started_at"
    inlines = [SessionAnswerInline, SessionResultInline]


@admin.register(SessionAnswer)
class SessionAnswerAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "question", "option",
                    "answered_at"]
    list_filter = ["answered_at"]
    search_fields = ["question__text_en", "option__label", "free_text"]
    raw_id_fields = ["session", "question", "option"]
    readonly_fields = ["answered_at"]


@admin.register(SessionResult)
class SessionResultAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "cause_name", "rank", "confidence"]
    list_filter = ["rank"]
    search_fields = ["cause__name", "explanation"]
    raw_id_fields = ["session", "cause"]
    readonly_fields = ["cause_name"]


@admin.register(Outcome)
class OutcomeAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "actual_cause",
                    "actual_cost", "was_helpful", "created_at"]
    list_filter = ["was_helpful", "created_at"]
    search_fields = ["actual_cause__name", "actual_cause_text", "notes"]
    raw_id_fields = ["session", "actual_cause", "mechanic"]

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "kind", "is_read", "created_at", "read_at")
    list_filter = ("kind", "read_at", "created_at")
    search_fields = ("user__username", "user__email", "kind", "dedupe_key")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    actions = ["mark_as_read", "mark_as_unread"]

    @admin.display(boolean=True, description="Read")
    def is_read(self, obj):
        return obj.read_at is not None

    @admin.action(description="Mark selected notifications as read")
    def mark_as_read(self, request, queryset):
        updated = queryset.filter(read_at__isnull=True).update(read_at=timezone.now())
        self.message_user(request, f"{updated} notification(s) marked as read.")

    @admin.action(description="Mark selected notifications as unread")
    def mark_as_unread(self, request, queryset):
        updated = queryset.filter(read_at__isnull=False).update(read_at=None)
        self.message_user(request, f"{updated} notification(s) marked as unread.")