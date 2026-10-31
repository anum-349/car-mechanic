from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "mechanic", "user", "rating", "work_quality",
                    "price_fairness", "communication", "timeliness", "status",
                    "created_at"]
    list_filter = ["status", "rating", "work_quality", "price_fairness",
                   "communication", "timeliness", "created_at"]
    search_fields = ["comment", "user__username", "mechanic__workshop_name"]
    raw_id_fields = ["user", "mechanic"]
    readonly_fields = ["created_at"]
    actions = ["approve", "reject"]

    @admin.action(description="Approve selected reviews")
    def approve(self, request, queryset):
        queryset.update(status=Review.Status.APPROVED)

    @admin.action(description="Reject selected reviews")
    def reject(self, request, queryset):
        queryset.update(status=Review.Status.REJECTED)