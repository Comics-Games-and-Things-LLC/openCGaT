from django.db.models import Sum
from rest_framework import serializers

from checkout.models import CheckoutLine, Cart
from digitalitems.models import DigitalItem
from images.serializers import ImageSerializer
from partner.serializers import PartnerSerializer
from .models import Item, Product, InventoryItem, MadeToOrder


class ProductSerializer(serializers.ModelSerializer):
    visible = serializers.SerializerMethodField()
    primary_image = ImageSerializer()

    class Meta:
        model = Product
        fields = ('id', 'name', 'slug', 'visible', 'primary_image')

    @staticmethod
    def get_visible(product):
        return product.visible


class ItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()
    type = serializers.SerializerMethodField()
    partner = PartnerSerializer()
    backorders_enabled = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()
    is_preorder = serializers.SerializerMethodField()
    is_pay_what_you_want = serializers.SerializerMethodField()
    button_status = serializers.SerializerMethodField()

    enable_restock_alert = serializers.SerializerMethodField()
    low_inventory_alert_threshold = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            'id', 'type', 'product', 'price', 'default_price', 'partner', 'inventory',
            'backorders_enabled', 'is_preorder', 'button_status', 'is_pay_what_you_want',
            'in_store_only_price',
            'enable_restock_alert', 'low_inventory_alert_threshold',
        )

    @staticmethod
    def get_type(item):
        return item.get_type()

    @staticmethod
    def get_inventory(item):
        if isinstance(item, InventoryItem) or isinstance(item, MadeToOrder):
            return item.get_inventory()
        else:
            return 0

    @staticmethod
    def get_is_pay_what_you_want(item):
        if isinstance(item, DigitalItem):
            return item.pay_what_you_want
        else:
            return False

    @staticmethod
    def get_backorders_enabled(item):
        if isinstance(item, InventoryItem):
            return item.allow_backorders
        elif isinstance(item, MadeToOrder):
            return True
        else:
            return False

    @staticmethod
    def get_is_preorder(item):
        return item.product.is_preorder

    def get_button_status(self, item):
        cart = self.context.get("cart")
        return item.button_status(cart=cart)

    @staticmethod
    def get_enable_restock_alert(item):
        if isinstance(item, InventoryItem):
            return item.enable_restock_alert
        return False

    @staticmethod
    def get_low_inventory_alert_threshold(item):
        if isinstance(item, InventoryItem):
            return item.low_inventory_alert_threshold
        return None


class ManageItemSerializer(ItemSerializer):
    sold_count = serializers.SerializerMethodField()

    class Meta(ItemSerializer.Meta):
        fields = ItemSerializer.Meta.fields + ('sold_count',)

    @staticmethod
    def get_sold_count(item):
        return int(CheckoutLine.objects.filter(item=item,
                                           cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED]) \
            .exclude(cancelled=True).aggregate(sum=Sum("quantity"))['sum'] or 0)
