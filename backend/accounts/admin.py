from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import MechanicProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["id", "username", "email", "name", "role", "city",
                    "language", "is_active"]
    list_filter = ["role", "language", "city", "is_active", "is_staff"]
    search_fields = ["username", "email", "name", "phone"]
    ordering = ["id"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("name", "phone", "city", "role", "language")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Profile", {"fields": ("email", "name", "phone", "city", "role",
                                "language")}),
    )


@admin.register(MechanicProfile)
class MechanicProfileAdmin(admin.ModelAdmin):
    list_display = ["workshop_name", "user", "address", "city",
                    "experience_years", "is_verified", "honesty_score"]
    list_filter = ["is_verified", "city"]
    search_fields = ["workshop_name", "address", "user__username", "user__email",
                     "user__phone"]
    raw_id_fields = ["user"]
    list_editable = ["is_verified"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["verify", "unverify"]

    @admin.action(description="Verify mechanic")
    def verify(self, request, queryset):
        queryset.update(is_verified=True)

    @admin.action(description="Remove verification from selected mechanics")
    def unverify(self, request, queryset):
        queryset.update(is_verified=False)
