from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from accounts.views import home_view
from diagnosis.notification_api import NotificationListView, NotificationReadView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path(f"{settings.ADMIN_URL}/", admin.site.urls),
    path("", home_view, name="home"),
    path("api/accounts/", include("accounts.urls")),
    path("api/", include("analytics.urls")),
    path("api/mechanic/", include("mechanic.urls")),
    path("api/garage/", include("garage.urls")),
    path("api/scam-check/", include("scamshield.urls")),
    path("api/knowledge/", include("knowledge.urls")),
    path("api/", include("knowledge.public_urls")),
    path("api/diagnosis/", include("diagnosis.urls")),
    path("api/", include("diagnosis.urls")),
    path("api/notifications/", NotificationListView.as_view(), name="notifications"),
    path("api/notifications/<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("api/scamshield/", include("scamshield.urls")),
    path("api/reviews/", include("reviews.urls")),
    path("api/review/", include("knowledge.review_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
