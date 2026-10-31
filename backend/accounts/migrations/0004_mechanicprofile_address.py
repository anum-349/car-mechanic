from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_delete_sequence_remove_mechanicprofile_code_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="mechanicprofile",
            name="address",
            field=models.CharField(blank=True, max_length=250),
        ),
    ]
