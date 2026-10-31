import django.core.validators
import django.utils.timezone
import garage.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("garage", "0001_initial")]

    operations = []

    for model_name in ("carmake", "carmodel", "car", "servicelog"):
        operations.extend([
            migrations.AddField(
                model_name=model_name,
                name="created_at",
                field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
                preserve_default=False,
            ),
            migrations.AddField(
                model_name=model_name,
                name="updated_at",
                field=models.DateTimeField(auto_now=True),
            ),
        ])

    operations.extend([
        migrations.AlterField(
            model_name="carmodel",
            name="year_from",
            field=models.PositiveIntegerField(validators=[
                django.core.validators.MinValueValidator(1980),
                django.core.validators.MaxValueValidator(garage.models.latest_model_year),
            ]),
        ),
        migrations.AlterField(
            model_name="carmodel",
            name="year_to",
            field=models.PositiveIntegerField(blank=True, null=True, validators=[
                django.core.validators.MinValueValidator(1980),
                django.core.validators.MaxValueValidator(garage.models.latest_model_year),
            ]),
        ),
        migrations.AlterField(
            model_name="carmodel",
            name="fuel_type",
            field=models.CharField(choices=[("petrol", "Petrol"), ("diesel", "Diesel"), ("hybrid", "Hybrid"), ("cng", "CNG")], default="petrol", max_length=20),
        ),
        migrations.AlterField(
            model_name="car",
            name="year",
            field=models.PositiveIntegerField(default=garage.models.current_year, validators=[
                django.core.validators.MinValueValidator(1980),
                django.core.validators.MaxValueValidator(garage.models.latest_model_year),
            ]),
        ),
        migrations.AlterField(
            model_name="car",
            name="mileage_km",
            field=models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name="car",
            name="transmission",
            field=models.CharField(choices=[("manual", "Manual"), ("automatic", "Automatic")], default="manual", max_length=20),
        ),
        migrations.AlterField(
            model_name="car",
            name="fuel_type",
            field=models.CharField(choices=[("petrol", "Petrol"), ("diesel", "Diesel"), ("hybrid", "Hybrid"), ("cng", "CNG")], default="petrol", max_length=20),
        ),
        migrations.AlterField(
            model_name="servicelog",
            name="mileage_km",
            field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
    ])
