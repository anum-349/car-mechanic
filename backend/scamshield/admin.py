from django.contrib import admin

from .models import ScamCheck


@admin.register(ScamCheck)
class ScamCheckAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "claimed_cause", "quoted_price",
                    "plausibility", "verdict", "created_at"]
    list_filter = ["verdict", "created_at"]
    search_fields = ["claim_text", "user__username", "user__email",
                     "claimed_cause__name"]
    raw_id_fields = ["user", "session", "claimed_cause"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"
