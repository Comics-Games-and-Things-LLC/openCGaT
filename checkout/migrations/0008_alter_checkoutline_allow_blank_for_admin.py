# Generated by Django 4.2.7 on 2024-02-10 18:31

from django.db import migrations, models
import django.db.models.deletion
import djmoney.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0003_remove_partner_css_filename'),
        ('checkout', '0007_allow_blank_for_admin_view'),
    ]

    operations = [
        migrations.AlterField(
            model_name='checkoutline',
            name='cancelled_timestamp',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='cart',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lines', to='checkout.cart'),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='fulfilled_in_cart',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lines_fulfilled', to='checkout.cart'),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='fulfilled_timestamp',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='name_of_item',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='paid_in_cart',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lines_paid', to='checkout.cart'),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='partner_at_time_of_submit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='partner.partner'),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='price_per_unit_at_submit',
            field=djmoney.models.fields.MoneyField(blank=True, decimal_places=2, max_digits=19, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='price_per_unit_override',
            field=djmoney.models.fields.MoneyField(blank=True, decimal_places=2, max_digits=19, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='ready_timestamp',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='submitted_in_cart',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lines_submitted', to='checkout.cart'),
        ),
        migrations.AlterField(
            model_name='checkoutline',
            name='tax_per_unit',
            field=djmoney.models.fields.MoneyField(blank=True, decimal_places=2, max_digits=19, null=True),
        ),
    ]
