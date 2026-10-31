import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0002_review_review_rating_between_one_five"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="work_quality",
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name="review",
            name="price_fairness",
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name="review",
            name="communication",
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5)]),
        ),
        migrations.AddField(
            model_name="review",
            name="timeliness",
            field=models.PositiveSmallIntegerField(blank=True, null=True,
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5)]),
        ),
    ]
