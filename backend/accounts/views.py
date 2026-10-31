from django.db.models import Q
from django.http import HttpResponse
from rest_framework import filters, generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import extend_schema

from .models import MechanicProfile
from .permissions import (IsAdminRole, IsMechanicRole, IsOwnerOrStaff,
                          is_staff_role)
from .serializers import (MechanicProfileSerializer, RegisterSerializer,
                          UserSerializer)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=RegisterSerializer, responses={201: RegisterSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class MechanicProfileViewSet(viewsets.ModelViewSet):
    serializer_class = MechanicProfileSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["workshop_name", "address", "city", "specialization"]
    ordering_fields = ["honesty_score", "experience_years"]
    queryset = MechanicProfile.objects.select_related("user").order_by("user_id")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        if self.action == "create":
            return [IsAuthenticated(), IsMechanicRole()]
        if self.action in ("verify", "unverify"):
            return [IsAdminRole()]
        return [IsAuthenticated(), IsOwnerOrStaff()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if is_staff_role(user):
            return qs
        if self.action in ("list", "retrieve"):
            cond = Q(is_verified=True)
            if user.is_authenticated:
                cond |= Q(user=user)
            return qs.filter(cond)
        return qs.filter(user=user) if user.is_authenticated else qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        if MechanicProfile.objects.filter(user=user).exists():
            raise ValidationError("You already have a mechanic profile.")
        serializer.save(user=user,
                        city=serializer.validated_data.get("city") or user.city)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        profile = self.get_object()
        profile.is_verified = True
        profile.save(update_fields=["is_verified"])
        return Response(self.get_serializer(profile).data)

    @action(detail=True, methods=["post"])
    def unverify(self, request, pk=None):
        profile = self.get_object()
        profile.is_verified = False
        profile.save(update_fields=["is_verified"])
        return Response(self.get_serializer(profile).data)

def home_view(request):
    return HttpResponse("This is car mechanic apis.")
