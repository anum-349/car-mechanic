from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.mixins import ParamFilterMixin
from accounts.permissions import (IsOwnerOrStaff, IsReviewerOrAdmin,
                                  is_staff_role)

from .models import Review
from .serializers import ReviewSerializer


class ReviewViewSet(ParamFilterMixin, viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    filter_params = {"mechanic": "mechanic_id", "status": "status"}

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        if self.action in ("approve", "reject"):
            return [IsReviewerOrAdmin()]
        if self.action == "create":
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsOwnerOrStaff()]

    def get_queryset(self):
        qs = Review.objects.select_related("user", "mechanic").order_by("-created_at", "-id")
        user = self.request.user
        if is_staff_role(user):
            return qs
        cond = Q(status=Review.Status.APPROVED)
        if user.is_authenticated:
            cond |= Q(user=user)  # you always see your own, even if pending
        return qs.filter(cond)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # status defaults to pending

    def perform_update(self, serializer):
        # An edited review goes back to moderation.
        serializer.save(status=Review.Status.PENDING)

    def _set(self, status):
        review = self.get_object()
        review.status = status
        review.save(update_fields=["status"])
        return Response(self.get_serializer(review).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._set(Review.Status.APPROVED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._set(Review.Status.REJECTED)
