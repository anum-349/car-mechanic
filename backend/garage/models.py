import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from core.models import TimeStampedModel


def current_year():
    return datetime.date.today().year


def latest_model_year():
    return current_year() + 1


class Transmission(models.TextChoices):
    MANUAL = "manual", "Manual"
    AUTOMATIC = "automatic", "Automatic"


class FuelType(models.TextChoices):
    PETROL = "petrol", "Petrol"
    DIESEL = "diesel", "Diesel"
    HYBRID = "hybrid", "Hybrid"
    CNG = "cng", "CNG"


class CarMake(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class CarModel(TimeStampedModel):
    car_make = models.ForeignKey(
        CarMake, on_delete=models.CASCADE, related_name="models"
    )
    name = models.CharField(max_length=100)
    generation = models.CharField(max_length=100, blank=True)
    year_from = models.PositiveIntegerField(
        validators=[MinValueValidator(1980), MaxValueValidator(latest_model_year)]
    )
    year_to = models.PositiveIntegerField(  # blank = still in production
        null=True, blank=True,
        validators=[MinValueValidator(1980), MaxValueValidator(latest_model_year)],
    )
    engine_cc = models.PositiveIntegerField(null=True, blank=True)
    fuel_type = models.CharField(
        max_length=20, choices=FuelType.choices, default=FuelType.PETROL
    )
    comment = models.CharField(max_length=250, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["car_make", "name", "generation"],
                name="unique_make_model_generation",
            )
        ]

    def __str__(self):
        return f"{self.car_make.name} {self.name} {self.generation}".strip()


class Car(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cars"
    )
    car_model = models.ForeignKey(CarModel, on_delete=models.PROTECT)
    nickname = models.CharField(max_length=100, blank=True)
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(1980), MaxValueValidator(latest_model_year)],
        default=current_year,
    )
    mileage_km = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    transmission = models.CharField(
        max_length=20, choices=Transmission.choices, default=Transmission.MANUAL
    )
    fuel_type = models.CharField(
        max_length=20, choices=FuelType.choices, default=FuelType.PETROL
    )

    def __str__(self):
        return self.nickname or f"{self.car_model} ({self.year})"


class ServiceLog(TimeStampedModel):
    car = models.ForeignKey(
        Car, on_delete=models.CASCADE, related_name="service_logs"
    )
    service_type = models.CharField(max_length=80)  # oil change, tyres...
    service_date = models.DateField()
    mileage_km = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    cost = models.PositiveIntegerField(null=True, blank=True)  # PKR
    next_due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-service_date"]

    def __str__(self):
        return f"{self.service_type} for {self.car} on {self.service_date}"
