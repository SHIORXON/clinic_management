from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0003_sutkalik_smena"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeprofile",
            name="permissions",
            field=models.JSONField(blank=True, default=list, verbose_name="Ruxsatlar"),
        ),
    ]
