from rest_framework import filters, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view

from accounts.mixins import ParamFilterMixin

from .models import Car, CarMake, CarModel, ServiceLog
from .serializers import (CarMakeSerializer, CarModelSerializer, CarSerializer,
                          ServiceLogSerializer)


class CarMakeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarMake.objects.all().order_by("name")
    serializer_class = CarMakeSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]


@extend_schema_view(
    list=extend_schema(summary="List car models for the vehicle picker"),
    retrieve=extend_schema(summary="Retrieve a car model"),
)
class CarModelViewSet(ParamFilterMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CarModel.objects.select_related("car_make").order_by(
        "car_make__name", "name", "year_from")
    serializer_class = CarModelSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "generation", "car_make__name"]
    filter_params = {"make": "car_make_id"}


@extend_schema_view(
    list=extend_schema(summary="List the authenticated user's cars"),
    create=extend_schema(summary="Add a car to the authenticated user's garage"),
    retrieve=extend_schema(summary="Retrieve one of the authenticated user's cars"),
    partial_update=extend_schema(summary="Update one of the authenticated user's cars"),
    destroy=extend_schema(summary="Delete one of the authenticated user's cars"),
)
class CarViewSet(viewsets.ModelViewSet):
    queryset = Car.objects.none()
    serializer_class = CarSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (Car.objects.filter(user=self.request.user)
                .select_related("car_model__car_make").order_by("-id"))

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ServiceLogViewSet(ParamFilterMixin, viewsets.ModelViewSet):
    queryset = ServiceLog.objects.none()
    serializer_class = ServiceLogSerializer
    permission_classes = [IsAuthenticated]
    filter_params = {"car": "car_id"}

    def get_queryset(self):
        return ServiceLog.objects.filter(car__user=self.request.user)
