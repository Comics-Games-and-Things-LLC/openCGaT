# Generated by Django 4.2.15 on 2024-08-25 23:33

from django.db import migrations
import djmoney.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('discount_codes', '0005_referrer_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='discountcode',
            name='min_cart_for_discount_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
    ]
