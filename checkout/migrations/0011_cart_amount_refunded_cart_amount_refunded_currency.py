# Generated by Django 4.2.10 on 2024-06-18 22:11

from django.db import migrations
import djmoney.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('checkout', '0010_alter_cart_managers_cart_broken_down'),
    ]

    operations = [
        migrations.AddField(
            model_name='cart',
            name='amount_refunded',
            field=djmoney.models.fields.MoneyField(blank=True, decimal_places=2, default_currency='USD', max_digits=19, null=True),
        ),
        migrations.AddField(
            model_name='cart',
            name='amount_refunded_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True),
        ),
    ]
