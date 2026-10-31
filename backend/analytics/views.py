from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import EventCreateSerializer
from .services import analytics_snapshot


class IsAnalyticsReviewer(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and
                    (user.is_superuser or user.role in {"reviewer", "admin"}))


class EventCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analytics"

    @extend_schema(request=EventCreateSerializer, responses={201: dict})
    def post(self, request):
        serializer = EventCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        return Response({"id": event.pk}, status=status.HTTP_201_CREATED)


class AdminAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsAnalyticsReviewer]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response(analytics_snapshot())
