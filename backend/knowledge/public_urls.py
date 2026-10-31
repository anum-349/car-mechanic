from django.urls import path

from .views import (PublicCategoriesView, PublicObdCodeView,
                    PublicWarningLightsView)

urlpatterns = [
    path("categories/", PublicCategoriesView.as_view(), name="public-categories"),
    path("warning-lights/", PublicWarningLightsView.as_view(), name="public-warning-lights"),
    path("obd/<str:code>/", PublicObdCodeView.as_view(), name="public-obd-code"),
]
