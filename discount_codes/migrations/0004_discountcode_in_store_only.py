# Generated by Django 4.2.6 on 2023-10-29 20:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('discount_codes', '0003_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='discountcode',
            name='in_store_only',
            field=models.BooleanField(default=False),
        ),
    ]
