# Generated by Django 4.2.15 on 2024-08-25 20:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0007_poline_distributor_code'),
        ('shop', '0009_inventoryitem_enable_restock_alert_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='publisher',
            name='available_through_distributors',
            field=models.ManyToManyField(blank=True, null=True, to='intake.distributor'),
        ),
    ]
