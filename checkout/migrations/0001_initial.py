# Generated by Django 4.2.2 on 2023-06-10 20:00

import address.models
import checkout.managers
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager
import django_react_templatetags.mixins
import djmoney.models.fields
import oscar.models.fields
import phonenumber_field.modelfields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('realaddress', '0001_initial'),
        ('address', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BillingAddress',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, choices=[('Mr', 'Mr'), ('Miss', 'Miss'), ('Mrs', 'Mrs'), ('Ms', 'Ms'), ('Dr', 'Dr')], max_length=64, verbose_name='Title')),
                ('first_name', models.CharField(blank=True, max_length=255, verbose_name='First name')),
                ('last_name', models.CharField(blank=True, max_length=255, verbose_name='Last name')),
                ('line1', models.CharField(max_length=255, verbose_name='First line of address')),
                ('line2', models.CharField(blank=True, max_length=255, verbose_name='Second line of address')),
                ('line3', models.CharField(blank=True, max_length=255, verbose_name='Third line of address')),
                ('line4', models.CharField(blank=True, max_length=255, verbose_name='City')),
                ('state', models.CharField(blank=True, max_length=255, verbose_name='State/County')),
                ('postcode', oscar.models.fields.UppercaseCharField(blank=True, max_length=64, verbose_name='Post/Zip-code')),
                ('search_text', models.TextField(editable=False, verbose_name='Search text - used only for searching addresses')),
            ],
            options={
                'verbose_name': 'Address',
                'verbose_name_plural': 'Addresses',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Cart',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('at_pos', models.BooleanField(default=False)),
                ('store_initiated_charge', models.BooleanField(default=False)),
                ('email', models.EmailField(max_length=254, null=True)),
                ('status', models.CharField(choices=[('Open', 'Open - currently active'), ('Merged', 'Merged - superseded by another cart'), ('Saved', 'Saved - for items to be purchased later'), ('Frozen', 'Frozen - the cart cannot be modified and is in checkout.'), ('Processing', 'Processing - the checkout process has begun and the cart is in limbo'), ('Submitted', 'Submitted - has completed checkout process, but not paid'), ('Paid', 'Paid - user has paid'), ('Completed', 'Complete - order has been delivered/picked up/etc'), ('Cancelled', 'Cancelled - Order was cancelled')], default='Open', max_length=128, verbose_name='Status')),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date created')),
                ('date_merged', models.DateTimeField(blank=True, null=True, verbose_name='Date merged')),
                ('date_processing', models.DateTimeField(blank=True, null=True, verbose_name='Date processing started')),
                ('date_submitted', models.DateTimeField(blank=True, null=True, verbose_name='Date submitted')),
                ('date_paid', models.DateTimeField(blank=True, null=True, verbose_name='Date paid')),
                ('delivery_method', models.CharField(blank=True, choices=[('Pickup All', 'Pickup all items in this order'), ('Ship All', 'Ship all items in this order')], default=None, max_length=128, null=True, verbose_name='delivery')),
                ('carrier', models.CharField(blank=True, choices=[('UPS', 'UPS'), ('USPS', 'USPS'), ('FEDEX', 'FEDEX'), ('DHL', 'DHL')], default=None, max_length=20, null=True, verbose_name='delivery')),
                ('payment_method', models.CharField(blank=True, choices=[('Pay via Stripe', 'Pay online via Credit or Debit Card'), ('Pay in store', 'Pay in person at the following store:')], default=None, max_length=128, null=True, verbose_name='payment')),
                ('delivery_name', models.CharField(blank=True, max_length=200, null=True)),
                ('delivery_apartment', models.CharField(blank=True, max_length=20, null=True)),
                ('as_guest', models.BooleanField(default=None, null=True)),
                ('final_total_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('final_total', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('final_tax_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('final_tax', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('final_ship_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('final_ship', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('final_digital_tax_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('final_digital_tax', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('final_physical_tax_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('final_physical_tax', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('cash_paid_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('cash_paid', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('total_paid_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('total_paid', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('set_in_taxjar', models.BooleanField(default=False)),
                ('tracking_number', models.CharField(blank=True, max_length=40, null=True)),
                ('ready_for_pickup', models.BooleanField(default=False)),
                ('postage_paid_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('postage_paid', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('expense_not_sale', models.BooleanField(default=False)),
                ('public_comments', models.TextField(blank=True, null=True)),
                ('private_comments', models.TextField(blank=True, null=True)),
                ('tax_error', models.TextField(blank=True, null=True)),
                ('address_error', models.JSONField(blank=True, null=True)),
                ('discount_code_message', models.TextField(max_length=True, null=True)),
            ],
            bases=(django_react_templatetags.mixins.RepresentationMixin, models.Model),
            managers=[
                ('open', checkout.managers.OpenCartManager()),
                ('saved', checkout.managers.SavedCartManager()),
                ('submitted', checkout.managers.SubmittedCartManager()),
            ],
        ),
        migrations.CreateModel(
            name='TaxRateCache',
            fields=[
                ('rate', models.DecimalField(decimal_places=6, max_digits=10, null=True)),
                ('location', models.CharField(max_length=100, primary_key=True, serialize=False)),
                ('updated', models.DateTimeField(auto_now=True)),
            ],
            managers=[
                ('taxes', django.db.models.manager.Manager()),
            ],
        ),
        migrations.CreateModel(
            name='UserDefaultAddress',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', address.models.AddressField(on_delete=django.db.models.deletion.CASCADE, to='address.address')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='default_address', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='StripePaymentIntent',
            fields=[
                ('for_subscription', models.BooleanField(default=False)),
                ('amount_to_pay_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default='USD', editable=False, max_length=3, null=True)),
                ('amount_to_pay', djmoney.models.fields.MoneyField(decimal_places=2, default_currency='USD', max_digits=19, null=True)),
                ('id', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('cancelled', models.BooleanField(default=False)),
                ('captured', models.BooleanField(default=False)),
                ('cart', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='checkout.cart')),
            ],
        ),
        migrations.CreateModel(
            name='StripeCustomerId',
            fields=[
                ('id', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='stripe_id', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ShippingAddress',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, choices=[('Mr', 'Mr'), ('Miss', 'Miss'), ('Mrs', 'Mrs'), ('Ms', 'Ms'), ('Dr', 'Dr')], max_length=64, verbose_name='Title')),
                ('first_name', models.CharField(blank=True, max_length=255, verbose_name='First name')),
                ('last_name', models.CharField(blank=True, max_length=255, verbose_name='Last name')),
                ('line1', models.CharField(max_length=255, verbose_name='First line of address')),
                ('line2', models.CharField(blank=True, max_length=255, verbose_name='Second line of address')),
                ('line3', models.CharField(blank=True, max_length=255, verbose_name='Third line of address')),
                ('line4', models.CharField(blank=True, max_length=255, verbose_name='City')),
                ('state', models.CharField(blank=True, max_length=255, verbose_name='State/County')),
                ('postcode', oscar.models.fields.UppercaseCharField(blank=True, max_length=64, verbose_name='Post/Zip-code')),
                ('search_text', models.TextField(editable=False, verbose_name='Search text - used only for searching addresses')),
                ('phone_number', phonenumber_field.modelfields.PhoneNumberField(blank=True, help_text='In case we need to call you about your order', max_length=128, region=None, verbose_name='Phone number')),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='realaddress.realcountry', verbose_name='Country')),
            ],
            options={
                'verbose_name': 'Address',
                'verbose_name_plural': 'Addresses',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CheckoutLine',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('qty_before_submit', models.PositiveIntegerField(blank=True, null=True)),
                ('price_per_unit_at_submit_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default=None, editable=False, max_length=3, null=True)),
                ('price_per_unit_at_submit', djmoney.models.fields.MoneyField(decimal_places=2, max_digits=19, null=True)),
                ('price_per_unit_override_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default=None, editable=False, max_length=3, null=True)),
                ('price_per_unit_override', djmoney.models.fields.MoneyField(decimal_places=2, max_digits=19, null=True)),
                ('tax_per_unit_currency', djmoney.models.fields.CurrencyField(choices=[('USD', 'US Dollar')], default=None, editable=False, max_length=3, null=True)),
                ('tax_per_unit', djmoney.models.fields.MoneyField(decimal_places=2, max_digits=19, null=True)),
                ('name_of_item', models.TextField(null=True)),
                ('fulfilled', models.BooleanField(default=False)),
                ('fulfilled_timestamp', models.DateTimeField(null=True)),
                ('ready', models.BooleanField(default=False)),
                ('ready_timestamp', models.DateTimeField(null=True)),
                ('cancelled', models.BooleanField(default=False)),
                ('cancelled_timestamp', models.DateTimeField(null=True)),
                ('back_or_pre_order', models.BooleanField(default=False)),
                ('discount_code_message', models.TextField(blank=True, null=True)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lines', to='checkout.cart')),
                ('fulfilled_in_cart', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lines_fulfilled', to='checkout.cart')),
            ],
            options={
                'ordering': ['-date_added'],
            },
        ),
    ]
