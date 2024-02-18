# Generated by Django 4.2.7 on 2024-02-18 00:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('partner', '0003_remove_partner_css_filename'),
        ('checkout', '0008_alter_checkoutline_allow_blank_for_admin'),
    ]

    operations = [
        migrations.CreateModel(
            name='BoxInventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=40)),
                ('length_inches', models.PositiveIntegerField()),
                ('width_inches', models.PositiveIntegerField()),
                ('height_inches', models.PositiveIntegerField()),
                ('barcode', models.CharField(max_length=40, unique=True)),
                ('current_inventory', models.PositiveIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='BoxUse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('box', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='box_counter.boxinventory')),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='used_boxes', to='checkout.cart')),
            ],
        ),
        migrations.CreateModel(
            name='BoxPurchase',
            fields=[
                ('date', models.DateField(null=True)),
                ('order_number', models.CharField(max_length=40, primary_key=True, serialize=False)),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='partner.partner')),
            ],
        ),
    ]
