from django.contrib import admin

from .models import Car, CarMake, CarModel, ServiceLog


@admin.register(CarMake)
class CarMakeAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ["id", "car_make", "name", "generation", "year_from",
                    "year_to", "engine_cc", "fuel_type"]
    list_filter = ["car_make", "fuel_type"]
    search_fields = ["name", "generation", "car_make__name"]
    autocomplete_fields = ["car_make"]
    readonly_fields = ["created_at", "updated_at"]


class ServiceLogInline(admin.TabularInline):
    model = ServiceLog
    extra = 0


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ["id", "nickname", "user", "car_model", "year",
                    "mileage_km", "transmission", "fuel_type"]
    list_filter = ["transmission", "fuel_type", "year"]
    search_fields = ["nickname", "user__username", "user__email",
                     "car_model__name", "car_model__car_make__name"]
    raw_id_fields = ["user"]
    autocomplete_fields = ["car_model"]
    inlines = [ServiceLogInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ServiceLog)
class ServiceLogAdmin(admin.ModelAdmin):
    list_display = ["id", "car", "service_type", "service_date",
                    "mileage_km", "cost", "next_due_date"]
    list_filter = ["service_type", "service_date"]
    search_fields = ["service_type", "car__nickname", "notes"]
    date_hierarchy = "service_date"
    raw_id_fields = ["car"]
    readonly_fields = ["created_at", "updated_at"]
