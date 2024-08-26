# Generated by Django 4.2.15 on 2024-08-26 23:10

from django.db import migrations
import djmoney.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('intake', '0008_purchaseorder_notes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='distributor',
            name='currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $'), ('GBP', 'GBP £')], default='USD', max_length=3),
        ),
        migrations.AlterField(
            model_name='distitem',
            name='dist_price_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='distitem',
            name='map_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='distitem',
            name='msrp_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='poline',
            name='cost_per_item',
            field=djmoney.models.fields.MoneyField(blank=True, currency_choices=[('USD', 'USD $'), ('GBP', 'GBP £')], decimal_places=4, max_digits=8, null=True),
        ),
        migrations.AlterField(
            model_name='poline',
            name='cost_per_item_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $'), ('GBP', 'GBP £')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='poline',
            name='msrp_on_line_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='purchaseorder',
            name='amount_charged_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $')], default='USD', editable=False, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='purchaseorder',
            name='subtotal',
            field=djmoney.models.fields.MoneyField(blank=True, currency_choices=[('USD', 'USD $'), ('GBP', 'GBP £')], decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AlterField(
            model_name='purchaseorder',
            name='subtotal_currency',
            field=djmoney.models.fields.CurrencyField(choices=[('USD', 'USD $'), ('GBP', 'GBP £')], default='USD', editable=False, max_length=3, null=True),
        ),
    ]
