from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "payload", "read_at", "created_at"]
        read_only_fields = fields


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=NotificationSerializer(many=True))
    def get(self, request):
        queryset = Notification.objects.filter(user=request.user).order_by("-created_at")
        pager = self.paginator_class()
        page = pager.paginate_queryset(queryset, request, view=self)
        data = NotificationSerializer(page, many=True).data
        response = pager.get_paginated_response(data)
        response.data["unread_count"] = queryset.filter(read_at__isnull=True).count()
        return response

    paginator_class = PageNumberPagination


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=NotificationSerializer)
    def post(self, request, pk):
        notification = Notification.objects.filter(user=request.user, pk=pk).first()
        if notification is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if notification.read_at is None:
            from django.utils import timezone
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)
