# Generated by Django 5.1.1 on 2024-09-14 05:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment_app', '0003_rename_bene_id_beneficiary_beneid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='beneficiary',
            name='bankAccount',
            field=models.CharField(blank=True, max_length=18, null=True, unique=True),
        ),
    ]