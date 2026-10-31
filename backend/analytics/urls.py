from django.urls import path

from .views import AdminAnalyticsView, EventCreateView

urlpatterns = [
    path("events/", EventCreateView.as_view(), name="analytics-events"),
    path("admin/analytics/", AdminAnalyticsView.as_view(), name="admin-analytics"),
]
