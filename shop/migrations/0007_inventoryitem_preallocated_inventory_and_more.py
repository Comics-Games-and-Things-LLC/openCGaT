# Generated by Django 4.2.11 on 2024-07-06 17:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0006_publisher_navbar_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitem',
            name='preallocated_inventory',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='inventorylog',
            name='after_preallocation_quantity',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='inventorylog',
            name='change_preallocation_quantity',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='inventorylog',
            name='is_preallocation_adjustment',
            field=models.BooleanField(default=False),
        ),
    ]
