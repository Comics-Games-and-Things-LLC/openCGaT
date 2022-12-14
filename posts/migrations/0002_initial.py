# Generated by Django 3.2.16 on 2022-11-22 19:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('shop', '0001_initial'),
        ('images', '0002_image_partner'),
        ('partner', '0001_initial'),
        ('posts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='products',
            field=models.ManyToManyField(to='shop.Product'),
        ),
        migrations.AddField(
            model_name='banner',
            name='image',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='images.image'),
        ),
        migrations.AddField(
            model_name='banner',
            name='partner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='partner.partner'),
        ),
    ]
