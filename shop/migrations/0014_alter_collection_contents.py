# Generated by Django 4.2.17 on 2025-04-04 21:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0013_collection'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='contents',
            field=models.ManyToManyField(related_name='in_collection', to='shop.product'),
        ),
    ]
