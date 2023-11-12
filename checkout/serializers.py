from django.urls import reverse
from rest_framework import serializers

from partner.serializers import PartnerSerializer
from shop.serializers import ItemSerializer
from .models import *


class CartLineSerializer(serializers.ModelSerializer):
    item = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    estimated_cost = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = CheckoutLine
        fields = ('item', 'quantity', 'price', 'estimated_cost', 'status',
                  'description', 'discount_code_message')

    @staticmethod
    def get_price(line):
        return float(line.get_price().amount)

    @staticmethod
    def get_item(line):
        if line.item:
            return ItemSerializer(line.item).data
        else:
            return {
                "partner": 'No longer available',
                "product": {'name': line.name_of_item},
                "id": None,
                "price": line.price_per_unit_at_submit.amount,
            }

    @staticmethod
    def get_estimated_cost(line):
        cost = line.get_estimated_store_cost()
        if cost:
            return float(cost.amount)

    @staticmethod
    def get_status(line):
        return line.status_text

    @staticmethod
    def get_description(line):
        if hasattr(line.item, "description"):
            return line.item.description


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = ('id', 'first_name', 'last_name', 'line1', 'line2', "line3", "line4",
                  "state", "country", "postcode", "phone_number")


class BillingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = ('id', 'first_name', 'last_name', 'line1', 'line2', "line3", "line4",
                  "state", "country", "postcode")


class CartSummarySerializer(serializers.ModelSerializer):
    estimated_total = serializers.SerializerMethodField()
    open = serializers.SerializerMethodField()
    owner_info = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('id', 'status', 'final_total', 'final_tax', 'username',
                  'estimated_total', 'open', 'total_paid', 'cash_paid', 'owner_info', 'owner', 'email')

    @staticmethod
    def get_owner_info(cart):
        if cart.owner:
            return "{} - {}".format(cart.owner.username, cart.owner.email)
        elif cart.email:
            return cart.email
        else:
            return "Anonymous"

    @staticmethod
    def get_username(cart):
        if cart.owner:
            return cart.owner.username
        return None

    @staticmethod
    def get_email(cart):
        if cart.owner:
            return cart.owner.email
        else:
            return cart.email

    @staticmethod
    def get_estimated_total(cart):
        return float(cart.get_estimated_total().amount)

    @staticmethod
    def get_open(cart):
        return cart.status == Cart.OPEN


class CartSerializer(CartSummarySerializer):
    lines = CartLineSerializer(many=True)
    payment_partner = PartnerSerializer()
    pickup_partner = PartnerSerializer()

    subtotal = serializers.SerializerMethodField()
    estimated_tax = serializers.SerializerMethodField()

    show_status_col = serializers.SerializerMethodField()

    shipping_address = ShippingAddressSerializer()
    billing_address = BillingAddressSerializer()

    available_pickup_partners = serializers.SerializerMethodField()

    is_shipping_required = serializers.SerializerMethodField()
    is_account_required = serializers.SerializerMethodField()
    in_store_pickup_only = serializers.SerializerMethodField()

    completed_steps = serializers.SerializerMethodField()
    ready_steps = serializers.SerializerMethodField()

    discount_code = serializers.SerializerMethodField()

    site = serializers.SerializerMethodField()

    is_free = serializers.SerializerMethodField()

    address_error = serializers.SerializerMethodField()

    disclaimer = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('id', 'status', 'lines', 'payment_partner', 'final_total', 'final_tax', 'subtotal',
                  'estimated_tax', 'estimated_total', 'open', 'final_ship', 'total_paid', 'cash_paid', 'owner_info',
                  'open', 'show_status_col', 'owner', 'email', 'username', 'shipping_address', 'billing_address',
                  'available_pickup_partners', 'is_shipping_required', 'pickup_partner', 'delivery_method',
                  'is_account_required', 'completed_steps', 'ready_steps', 'address_error',
                  'discount_code', 'discount_code_message', 'site', 'is_free', 'in_store_pickup_only', "disclaimer")

    @staticmethod
    def get_subtotal(cart):
        return float(cart.get_total_subtotal().amount)

    @staticmethod
    def get_address_error(cart):
        return json.dumps(cart.address_error)

    @staticmethod
    def get_estimated_tax(cart):
        return float(cart.get_tax().amount)

    @staticmethod
    def get_show_status_col(cart):
        return cart.not_only_digital

    @staticmethod
    def get_available_pickup_partners(cart):
        partners = cart.get_pickup_partners()
        partners_serialized = []
        for partner in partners:
            partners_serialized.append(PartnerSerializer(partner).data)
        return partners_serialized

    @staticmethod
    def get_is_shipping_required(cart):
        return cart.is_shipping_required()

    @staticmethod
    def get_is_account_required(cart):
        return cart.is_account_required()

    @staticmethod
    def get_completed_steps(cart):
        return cart.completed_steps()

    @staticmethod
    def get_ready_steps(cart):
        return cart.ready_steps()

    @staticmethod
    def get_discount_code(cart):
        if cart.discount_code:
            return cart.discount_code.code

    @staticmethod
    def get_site(cart):
        return cart.site.domain

    @staticmethod
    def get_is_free(cart):
        return cart.is_free()

    @staticmethod
    def get_in_store_pickup_only(cart):
        return cart.in_store_pickup_only

    @staticmethod
    def get_disclaimer(cart):
        return cart.get_disclaimer_text()


def get_pos_props(partner, cart_id=None):
    open_carts = Cart.open.filter(at_pos=True, payment_partner=partner)
    pay_in_store_carts = Cart.submitted.filter(payment_partner=partner, status=Cart.SUBMITTED)
    pickup_carts = Cart.submitted.filter(pickup_partner=partner, status=Cart.PAID)
    active_cart = None
    url = reverse('pos', kwargs={'partner_slug': partner.slug})[:-1]
    if cart_id:
        active_cart = Cart.objects.get(id=cart_id)
    return {'active_cart': CartSerializer(active_cart).data,
            'open_carts': CartSummarySerializer(open_carts, many=True).data,
            'pay_in_store_carts': CartSummarySerializer(pay_in_store_carts, many=True).data,
            'pickup_carts': CartSummarySerializer(pickup_carts, many=True).data,
            'url': url
            }
