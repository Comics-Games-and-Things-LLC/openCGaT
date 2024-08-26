import decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.forms import HiddenInput
from djmoney.forms import MoneyField
from djmoney.money import Money

from shop.forms import AddProductForm
from .models import PricingRule, PurchaseOrder, POLine, DistributorInventoryFile


class RefreshForm(forms.Form):
    distributor = forms.CharField(required=False)
    purchase_order = forms.CharField(required=False)
    add_mode = forms.BooleanField(required=False)
    auto_load = forms.BooleanField(required=False)
    auto_print_mode = forms.BooleanField(required=False)
    barcode = forms.CharField(required=False)
    quantity = forms.IntegerField(required=True)

    def __init__(self, *args, **kwargs):
        partner = kwargs.pop('partner')
        super(RefreshForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        if quantity < 0:
            msg = ValidationError("Quantity must not be negative")
            self.add_error('quantity', msg)


class AddForm(AddProductForm):
    our_price = MoneyField(default_currency='USD')


class UploadInventoryForm(forms.ModelForm):
    class Meta:
        model = DistributorInventoryFile
        fields = ['distributor', 'file']


class PrintForm(forms.Form):
    print_msrp = forms.CharField(required=False, widget=HiddenInput)
    print_price = forms.CharField(required=True, widget=HiddenInput)
    print_name = forms.CharField(required=False, widget=HiddenInput)


class PricingRuleForm(forms.ModelForm):
    class Meta:
        model = PricingRule
        fields = ['percent_of_msrp', 'priority', 'publisher', 'use_MAP']


class POForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['distributor', 'date', 'date_received', 'po_number', 'subtotal', 'amount_charged',
                  'separate_invoice_number', 'notes',
                  ]


class POLineForm(forms.ModelForm):
    subtotal = MoneyField(default_currency='USD', required=False)

    class Meta:
        model = POLine
        fields = ['name', 'barcode', 'distributor_code', 'line_number',
                  'expected_quantity', 'received_quantity',
                  'msrp_on_line',
                  'cost_per_item',
                  'pricing',
                  'subtotal',
                  ]

    def __init__(self, *args, **kwargs):
        po = kwargs.pop('po', None)
        self.expected_discount = None
        super(POLineForm, self).__init__(*args, **kwargs)

        self.fields['cost_per_item'].required = False
        self.fields['subtotal'].help_text = "Set cost per line or subtotal and expected quantity"
        if self.instance and hasattr(self.instance, 'po'):
            po = self.instance.po

        self.set_line_number_help_text(po)
        self.hide_pricing_element(po)
        self.set_msrp_and_cost_help_text(po)

    def set_line_number_help_text(self, po):
        if not (po and po.lines):
            return
        current_highest_line = po.lines.aggregate(Max('line_number'))["line_number__max"]
        number_of_numbered_lines = po.lines.filter(line_number__gt=0).count()
        if current_highest_line == number_of_numbered_lines:
            self.fields['line_number'].help_text = f"{current_highest_line + 1}, Based on: "
        self.fields['line_number'].help_text += f"Highest line: {current_highest_line}, " \
                                                f"Lines with numbers: {number_of_numbered_lines}"

    def hide_pricing_element(self, po):
        if not (po and po.distributor.dist_has_pricing_col):
            self.fields['pricing'].widget = forms.HiddenInput()

    def set_msrp_and_cost_help_text(self, po):
        if not (self.instance and self.instance.product):
            return
        msrp = self.instance.product.msrp
        self.fields['msrp_on_line'].help_text = str(msrp)
        self.expected_discount = po.get_distributor_discount(self.instance)

        if not (self.expected_discount and msrp):
            return
        expected_cost = msrp - (msrp * self.expected_discount.discount_percentage / 100)
        self.fields['cost_per_item'].help_text = f"{expected_cost} at {self.expected_discount.discount_percentage}% off"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('subtotal') and not cleaned_data.get('cost_per_item'):
            cpi = cleaned_data['subtotal'] / cleaned_data['expected_quantity']
            cpi = Money(cpi.amount.quantize(FOUR_PLACES), 'USD', decimal_places=4)
            cleaned_data['cost_per_item'] = cpi
        return cleaned_data


FOUR_PLACES = decimal.Decimal("0.0001")
