# Generated by Django 4.2.15 on 2024-08-25 23:33

from django.db import migrations
import djmoney.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('checkout', '0011_cart_amount_refunded_cart_amount_refunded_currency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cart',
            name='amount_refunded_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='cash_paid_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='final_digital_tax_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='final_physical_tax_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='final_ship_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='final_tax_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='final_total_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='postage_paid_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='cart',
            name='total_paid_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='price_per_unit_at_submit_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='price_per_unit_override_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='tax_per_unit_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='stripepaymentintent',
            name='amount_to_pay_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
    ]
