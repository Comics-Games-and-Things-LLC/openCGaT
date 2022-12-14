# Generated by Django 3.2.16 on 2022-11-22 19:59

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Backer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email_address', models.EmailField(max_length=254)),
                ('backing_minimum', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('pledge_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
            ],
            managers=[
                ('records', django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name='CrowdfundCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('currency_conversion_rate', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('platform_cut', models.DecimalField(decimal_places=2, default=0.05, max_digits=10)),
                ('charge_date', models.DateField()),
            ],
        ),
        migrations.CreateModel(
            name='Reward',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('external_name', models.CharField(max_length=200)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crowdfund.crowdfundcampaign')),
            ],
        ),
        migrations.CreateModel(
            name='CrowdfundTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(max_length=200)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crowdfund.crowdfundcampaign')),
            ],
        ),
    ]
