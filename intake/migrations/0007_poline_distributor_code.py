# Generated by Django 4.2.10 on 2024-06-24 21:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0006_purchaseorder_date_received_alter_purchaseorder_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='poline',
            name='distributor_code',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
