# Generated by Django 5.1.1 on 2024-09-14 06:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payment_app', '0004_alter_beneficiary_bankaccount'),
    ]

    operations = [
        migrations.RenameField(
            model_name='beneficiary',
            old_name='bankAccount',
            new_name='bank_account',
        ),
        migrations.RenameField(
            model_name='beneficiary',
            old_name='beneId',
            new_name='beneficiary_id',
        ),
        migrations.RenameField(
            model_name='beneficiary',
            old_name='pincode',
            new_name='postal_code',
        ),
    ]
