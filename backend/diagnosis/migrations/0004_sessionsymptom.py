import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diagnosis", "0003_remove_sessionanswer_one_answer_per_question_and_more"),
        ("knowledge", "0006_cause_proof_hint"),
    ]

    operations = [
        migrations.CreateModel(
            name="SessionSymptom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("free_text", "Free text")],
                                             default="free_text", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="session_symptoms",
                                              to="diagnosis.diagnosissession")),
                ("symptom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                               related_name="session_symptoms",
                                               to="knowledge.symptom")),
            ],
        ),
        migrations.AddConstraint(
            model_name="sessionsymptom",
            constraint=models.UniqueConstraint(fields=("session", "symptom", "source"),
                                               name="unique_session_symptom_source"),
        ),
    ]
