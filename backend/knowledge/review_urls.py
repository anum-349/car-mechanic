from django.urls import path

from .review_api import LaunchGateView, ReviewQueueView, ReviewItemView, action_view

urlpatterns = [
    path("launch-gate/", LaunchGateView.as_view(), name="review-launch-gate"),
    path("queue/", ReviewQueueView.as_view(), name="review-queue"),
    path("items/<str:item_type>/<int:item_id>/", ReviewItemView.as_view(), name="review-item"),
    path("items/<str:item_type>/<int:item_id>/start/", action_view("start"), name="review-start"),
    path("items/<str:item_type>/<int:item_id>/approve/", action_view("approve"), name="review-approve"),
    path("items/<str:item_type>/<int:item_id>/return/", action_view("return"), name="review-return"),
    path("items/<str:item_type>/<int:item_id>/reject/", action_view("reject"), name="review-reject"),
    path("items/<str:item_type>/<int:item_id>/publish/", action_view("publish"), name="review-publish"),
]
