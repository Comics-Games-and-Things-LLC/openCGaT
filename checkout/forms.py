import djmoney as djmoney
from address.models import Country, State
from allauth.account.models import EmailAddress
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from oscar.forms.mixins import PhoneNumberMixin
from wagtail.users.forms import User

from partner.models import Partner
from realaddress.models import UserAddress
from .models import Cart, ShippingAddress, BillingAddress


class EmailForm(forms.ModelForm):
    class Meta:
        model = Cart
        fields = ['email']


class AbstractAddressForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        """
        Set fields in OSCAR_REQUIRED_ADDRESS_FIELDS as required.
        """
        super().__init__(*args, **kwargs)
        field_names = (set(self.fields)
                       & set(settings.OSCAR_REQUIRED_ADDRESS_FIELDS))
        for field_name in field_names:
            self.fields[field_name].required = True


class UserAddressForm(PhoneNumberMixin, AbstractAddressForm):
    class Meta:
        model = UserAddress
        fields = [
            'first_name', 'last_name',
            'line1', 'line2', 'line3', 'line4',
            'state', 'postcode', 'country',
            'phone_number', 'notes',
        ]

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.user = user


class BillingAddressForm(AbstractAddressForm):
    class Meta:
        model = BillingAddress
        fields = [
            'first_name', 'last_name',
            'line1', 'line2', 'line3', 'line4',
            'state', 'postcode', 'country',
        ]

    # existing_address = forms.ModelChoiceField(UserAddress.objects.none())

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.user = user
        # self.fields['existing_address'].queryset = UserAddress.objects.filter(user=user)


class ShippingAddressForm(PhoneNumberMixin, AbstractAddressForm):
    class Meta:
        model = ShippingAddress
        fields = [
            'first_name', 'last_name',
            'line1', 'line2', 'line3', 'line4',
            'state', 'postcode', 'country',
            'phone_number',
        ]

    # existing_address = forms.ModelChoiceField(UserAddress.objects.none())

    def __init__(self, user=None, *args, **kwargs):
        super(ShippingAddressForm, self).__init__(*args, **kwargs)
        # self.instance.user = user
        # self.fields['existing_address'].queryset = UserAddress.objects.filter(user=user)


class PickupForm(forms.ModelForm):
    class Meta:
        model = Cart
        fields = ['delivery_method', 'pickup_partner']

    def __init__(self, *args, **kwargs):
        super(PickupForm, self).__init__(*args, **kwargs)
        self.fields['pickup_partner'].queryset = Partner.objects.filter(retail_partner=True, hide=False)

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("delivery_method")
        pickup_partner = cleaned_data.get("pickup_partner")
        print(method, pickup_partner)
        if method is None:
            self.add_error('delivery_method', "Please select a method")
        if method == Cart.SHIP_ALL and pickup_partner is not None:
            msg = ValidationError("Please do not put a pickup partner if not picking up in-store")
            self.add_error('pickup_partner', msg)
        if method == Cart.PICKUP_ALL and pickup_partner is None:
            msg = ValidationError("Please specify a partner to pick up your order at")
            self.add_error('pickup_partner', msg)
        if method == Cart.SHIP_ALL and not self.instance.can_ship:
            msg = ValidationError("An item in your cart is not eligible to be shipped")
            self.add_error('delivery_method', msg)


class PaymentMethodForm(forms.ModelForm):
    """
    This form will always set pay in store on the cart if the partner is valid.
    """

    class Meta:
        model = Cart
        fields = ['payment_method', 'payment_partner']

    def __init__(self, *args, **kwargs):
        super(PaymentMethodForm, self).__init__(*args, **kwargs)
        if self.instance.pickup_partner:
            self.fields['payment_partner'].queryset = Partner.objects.filter(id=self.instance.pickup_partner.id)
            self.fields['payment_partner'].initial = self.instance.pickup_partner
        else:
            self.fields['payment_partner'].queryset = Partner.objects.filter(retail_partner=True, hide=False)

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("payment_method")
        payment_partner = cleaned_data.get("payment_partner")
        if method is None:
            self.add_error('payment_method', "Please select a method")
        if method == Cart.PAY_STRIPE and payment_partner is not None:
            self.add_error('payment_partner', "Please do not specify a location when paying online")
        if method == Cart.PAY_IN_STORE and payment_partner is None:
            self.add_error('payment_partner', "Please select a location to pay for your order ")


class TrackingInfoForm(forms.ModelForm):
    used_box_barcodes = forms.CharField(required=False)

    class Meta:
        model = Cart
        fields = ['tracking_number', 'carrier', 'postage_paid']


class PartnerCommentsForm(forms.ModelForm):
    class Meta:
        model = Cart
        fields = ['public_comments', 'private_comments']


class FiltersForm(forms.Form):
    order_id = forms.IntegerField(required=False)
    user = forms.CharField(required=False)

    SORT_RELEASE_DATE = "release_date"
    SORT_UPDATE_DATE = "update_date"
    SORT_PRICE = "price"

    status = forms.MultipleChoiceField(initial=[Cart.SUBMITTED, Cart.PAID],
                                       widget=forms.CheckboxSelectMultiple,
                                       choices=Cart.SUBMITTED_STATUS_CHOICES,
                                       required=False)

    state = forms.ModelChoiceField(State.objects.all(), required=False)
    country = forms.ModelChoiceField(Country.objects.all(), required=False)

    def get_orders(self, orders=None):
        if orders is None:
            orders = Cart.submitted.all()
        if self.is_valid():

            search_string = self.cleaned_data.get("user")
            customers = User.objects.all()

            if search_string:
                username_customers = customers.filter(username__icontains=search_string)
                email_addresses = EmailAddress.objects.filter(email__icontains=search_string)
                customers = username_customers | customers.filter(id__in=email_addresses.values_list('user_id'))
                orders = orders.filter(owner__in=customers) | orders.filter(email__search=search_string)
            status_filters = self.cleaned_data.get("status")
            if status_filters:
                orders = orders.filter(status__in=status_filters)
            order_id = self.cleaned_data.get("order_id")
            if order_id:
                orders = Cart.submitted.filter(id=order_id)
            state = self.cleaned_data.get("state")
            print(state)
            if state is not None:
                orders = orders.filter(delivery_address__locality__state=state) \
                         | orders.filter(delivery_address__locality__state=state) \
                         | orders.filter(payment_partner__address__locality__state=state) \
                         | orders.filter(pickup_partner__address__locality__state=state)

            country = self.cleaned_data.get("country")
            print(country)
            if country is not None:
                orders = orders.filter(delivery_address__locality__state__country=country) \
                         | orders.filter(delivery_address__locality__state__country=country) \
                         | orders.filter(payment_partner__address__locality__state__country=country) \
                         | orders.filter(pickup_partner__address__locality__state__country=country)

        else:
            orders = orders.filter(status__in=[Cart.SUBMITTED, Cart.PAID])
        return orders.distinct()


class PaymentAmountForm(forms.Form):
    amount = djmoney.forms.MoneyField()
