import json
from datetime import datetime
from decimal import Decimal, ROUND_UP

from b2sdk.exception import FileNotPresent
from django.apps import apps
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.db import models, transaction
from django.db.models import Sum
from django.template.defaultfilters import slugify
from django.template.loader import get_template
from django.utils import timezone
from django_react_templatetags.mixins import RepresentationMixin
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from mptt.models import MPTTModel, TreeForeignKey
from polymorphic.models import PolymorphicModel
from polymorphic.query import PolymorphicQuerySet
from wagtail.fields import RichTextField

from images.models import Image
from partner.models import Partner


class Publisher(models.Model):
    name = models.CharField(max_length=200)
    navbar_order = models.IntegerField(null=True, blank=True,
                                       help_text="If populated, will appear in navbar, highest first")
    no_discount_codes = models.BooleanField(default=False,
                                            help_text="If set, discount codes cannot apply at all")

    available_through_distributors = models.ManyToManyField("intake.Distributor", null=True, blank=True)

    def __str__(self):
        return self.name


class Category(MPTTModel):
    name = models.CharField(max_length=200)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_product_line = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class CardCondition(models.Model):
    condition_shorthand = models.CharField(max_length=10)
    condition_description = models.CharField(max_length=200)

    def __str__(self):
        return self.condition_shorthand


class ProductQuerySet(PolymorphicQuerySet):
    def filter_preorder_or_secondary_release_date(self, manage=False, date=None):
        if date is None:
            date = datetime.now()
        return self.remove_drafts(manage).filter(preorder_or_secondary_release_date__isnull=False,
                                                 preorder_or_secondary_release_date__lte=date)

    def filter_release_date(self, manage=False, date=None):
        if date is None:
            date = datetime.now()
        return self.remove_drafts(manage).filter(release_date__isnull=False,
                                                 release_date__lte=date)

    def remove_drafts(self, manage=False):
        if not manage:
            return self.exclude(page_is_draft=True)
        return self

    def filter_visible(self, manage=False):
        """Does not respect item-level overrides"""
        preorder_date_products = self.filter_preorder_or_secondary_release_date(manage) \
            .filter(visible_on_preorder_secondary=True)
        release_date_products = self.filter_release_date(manage).filter(visible_on_release=True)
        products = preorder_date_products | release_date_products
        products = products.distinct() | self.filter_listed(manage) | self.filter_purchasable(manage)
        return products.distinct()

    def filter_listed(self, manage=False):
        """Does not respect item-level overrides"""
        preorder_date_products = self.filter_preorder_or_secondary_release_date(manage) \
            .filter(listed_on_preorder_secondary=True)
        release_date_products = self.filter_release_date(manage).filter(listed_on_release=True)
        products = preorder_date_products | release_date_products
        return products.distinct()

    def filter_purchasable(self, manage=False):
        """Does not respect item-level overrides"""
        preorder_date_products = self.filter_preorder_or_secondary_release_date(manage) \
            .filter(purchasable_on_preorder_secondary=True)
        release_date_products = self.filter_release_date(manage).filter(purchasable_on_release=True)
        products = preorder_date_products | release_date_products
        return products.distinct()


class Product(PolymorphicModel):
    objects = ProductQuerySet.as_manager()

    # Old image upload, depricated
    main_image = models.ForeignKey('ProductImage', on_delete=models.SET_NULL, blank=True, null=True)
    image_gallery = models.ManyToManyField('ProductImage', blank=True, related_name='partner_images')
    # End old image upload

    primary_image = models.ForeignKey('images.Image', on_delete=models.SET_NULL, blank=True, null=True)
    attached_images = models.ManyToManyField('images.Image', blank=True, related_name='products')
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, blank=True, null=True)
    all_retail = models.BooleanField(default=False)

    name = models.CharField(max_length=200, unique=True)
    barcode = models.CharField(max_length=20, unique=True, blank=True, null=True)
    needs_barcode_printed = models.BooleanField(default=False)

    publisher_sku = models.CharField(max_length=30, blank=True, null=True)
    publisher_short_sku = models.CharField(max_length=10, blank=True, null=True, help_text="GW Short Code")
    weight = models.FloatField(blank=True, null=True)
    in_store_pickup_only = models.BooleanField(default=False)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, null=True, blank=True)
    product_line_id = models.CharField(max_length=200, null=True, blank=True)
    categories = models.ManyToManyField(Category, blank=True)

    VISIBLE_HELP_TEXT = "The page of a visible item can be viewed and any digital versions downloaded"
    PURCHASABLE_HELP_TEXT = "A purchasable item can be purchased, and will also be visible"
    LISTED_HELP_TEXT = "A listed item will be listed in the store, and will also be visible"

    release_date = models.DateField('Date released', null=True, blank=True,
                                    help_text="YYYY-MM-DD or MM/DD/YYYY, required for a non-draft")
    date_inaccurate = models.BooleanField("This date may be inaccurate", default=False)

    purchasable_on_release = models.BooleanField("Purchasable on above date", default=False,
                                                 help_text=PURCHASABLE_HELP_TEXT)
    listed_on_release = models.BooleanField("Listed on above date", default=False,
                                            help_text=LISTED_HELP_TEXT)
    visible_on_release = models.BooleanField("Visible on above date", default=False,
                                             help_text=VISIBLE_HELP_TEXT)
    preorder_or_secondary_release_date = models.DateField('Date accepting pre-orders or after-release orders',
                                                          null=True, blank=True,
                                                          help_text="YYYY-MM-DD or MM/DD/YYYY")
    purchasable_on_preorder_secondary = models.BooleanField("Purchasable on above date", default=False,
                                                            help_text=PURCHASABLE_HELP_TEXT)
    listed_on_preorder_secondary = models.BooleanField("Listed on above date", default=False,
                                                       help_text=LISTED_HELP_TEXT)
    visible_on_preorder_secondary = models.BooleanField("Visible on above date", default=False,
                                                        help_text=VISIBLE_HELP_TEXT)

    page_is_draft = models.BooleanField("Draft (unpublished)", default=True)

    page_is_template = models.BooleanField(default=False, help_text="An unpublished page that can be easily copied")

    # A product will be visible if page_visible is checked, if past the pre-order date and accepts pre-orders is checked
    # or after release_date. A product will be purchasable if past the pre-order date if accepts pre-orders is checked
    # or past release date otherwise.

    description = RichTextField(blank=True, null=True, features=['h2', 'h3', 'bold', 'italic', 'ol', 'ul'])

    msrp = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', null=True, blank=True)
    map = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', null=True, blank=True)

    slug = models.SlugField(unique=True, blank=True, max_length=200)

    games = models.ManyToManyField('game_info.Game', blank=True)
    editions = models.ManyToManyField('game_info.Edition', blank=True)
    formats = models.ManyToManyField('game_info.Format', blank=True)
    factions = models.ManyToManyField('game_info.Faction', blank=True)
    attributes = models.ManyToManyField('game_info.Attribute', blank=True)
    contents = models.ManyToManyField('game_info.GamePiece', blank=True)

    replaced_by = models.ForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL, related_name='replaces',
                                    help_text="If there is a  newer version of this product, reference it here")

    contains_product = models.ForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL,
                                         related_name='contained_in',
                                         help_text="If this item contains a multiple of another product, list it here")
    contains_number = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        if not self.release_date:
            self.page_is_draft = True
        if self.page_is_template:
            self.page_is_draft = True
        if self.purchasable_on_release or self.listed_on_release:
            self.visible_on_release = True
        if self.purchasable_on_preorder_secondary or self.listed_on_preorder_secondary:
            self.visible_on_preorder_secondary = True
        if self.id:  # Product must exist before we can use M2M relationships
            if self.attached_images and self.primary_image and not self.attached_images.filter(
                    id=self.primary_image.id).exists():
                self.primary_image = None
        super(Product, self).save(*args, **kwargs)

    @property
    def after_release_date(self, date=None):
        if date is None:
            date = datetime.now().date()
        return self.release_date and self.release_date <= date

    @property
    def after_secondary_date(self, date=None):
        if date is None:
            date = datetime.now().date()
        return self.preorder_or_secondary_release_date and self.preorder_or_secondary_release_date <= date

    @property
    def only_one_item(self, partner=None):
        return self.items_set.filter(partner=partner).count() <= 1

    @property
    def published(self):
        return self.item_set.exists() and not self.page_is_draft

    @property
    def should_be_listed(self):
        return (self.after_release_date and self.listed_on_release) or \
            (self.after_secondary_date and self.listed_on_preorder_secondary)

    @property
    def listed(self):
        return self.published and self.should_be_listed

    @property
    def should_be_purchasable(self):
        return (self.after_release_date and self.purchasable_on_release) or \
            (self.after_secondary_date and self.purchasable_on_preorder_secondary)

    @property
    def purchasable(self):
        return self.published and self.should_be_purchasable

    @property
    def should_be_visible(self):
        return (self.after_release_date and self.visible_on_release) or \
            (self.after_secondary_date and self.visible_on_preorder_secondary)

    @property
    def visible(self):
        return self.published and (self.should_be_visible or self.should_be_purchasable or self.should_be_listed)

    @property
    def visibility_reason(self):
        if self.should_be_purchasable:
            return "Purchasable so must be visible"
        if self.should_be_listed:
            return "Listed so must be visible"
        if self.should_be_visible:
            if self.after_release_date and self.visible_on_release:
                return "After release date"
            if self.after_secondary_date and self.visible_on_preorder_secondary:
                return "After preorder or secondary release date"
        else:
            if self.visible_on_release:
                return "Not after release date"
            if self.visible_on_preorder_secondary:
                return "Not after preorder or secondary release date"

    @property
    def preorder_date(self):
        """
        Replaces the previous preorder date property. Also requires release_date
        :return:
        """
        if self.preorder_or_secondary_release_date and self.release_date:
            if self.preorder_or_secondary_release_date <= self.release_date:
                return self.preorder_or_secondary_release_date
        return None

    @property
    def is_before_release(self):
        """
        More generic than is_preorder, including time before the product officially goes up for preorder.
        @return:
        """
        return self.release_date and datetime.today().date() < self.release_date

    @property
    def is_preorder(self):
        """
        Returns if the item is available for order and that order is a preorder.
        @return:
        """
        if self.preorder_or_secondary_release_date and self.release_date:
            if self.preorder_or_secondary_release_date <= self.release_date:
                if self.preorder_or_secondary_release_date <= datetime.today().date():
                    # print("In pre-order window")
                    if self.release_date:
                        if datetime.today().date() < self.release_date:
                            # print("Not yet released")
                            return True
                        else:
                            # print("Released")
                            return False
                    else:
                        # print("No release date specified")
                        return True
                else:
                    # print("Not in preorder window")
                    return False
            else:
                # print("Not a preorder date")
                return False
        else:
            # print("No secondary date")
            return False

    @property
    def all_images(self):
        return Image.objects.filter(products=self)

    def all_inventory_for_partner(self, partner):
        return InventoryItem.objects.filter(product=self, partner=partner).aggregate(sum=Sum("current_inventory"))[
            'sum']

    def lowest_price_for_type(self, item_model):
        lowest = None
        try:
            for item in item_model.objects.filter(product=self):
                if lowest is None:
                    lowest = item.price
                else:
                    if lowest > item.price:
                        lowest = item.price
        except item_model.DoesNotExist:
            return None
        return lowest

    def lowest_inventory_price(self):
        return self.lowest_price_for_type(InventoryItem)

    def lowest_digital_price(self):
        return self.lowest_price_for_type(apps.get_model('digitalitems.DigitalItem'))

    def lowest_mto_price(self):
        return self.lowest_price_for_type(MadeToOrder)

    def get_price_rule(self, partner):
        rules = apps.get_model('intake.PricingRule').objects.filter(partner=partner)
        selected_rule = None
        try:
            selected_rule = rules.filter(publisher__isnull=True).latest('priority')
        except Exception:
            pass
        if self.publisher:
            try:
                selected_rule = rules.filter(publisher=self.publisher).latest('priority')
            except Exception:
                pass
        return selected_rule

    def get_price_from_rule(self, partner):
        if self.msrp:
            selected_rule = self.get_price_rule(partner)
            if selected_rule:
                if selected_rule.use_MAP and self.map is not None:
                    return self.map
                else:
                    if hasattr(self.msrp, 'amount'):
                        price = Money(Decimal(Decimal(selected_rule.percent_of_msrp) / Decimal(100) * self.msrp.amount).quantize(
                            Decimal('.01'), rounding=ROUND_UP),
                                      'USD', decimal_places=2)
                        if self.map:
                            return max([self.map, price])
                        return price
        return None

    def get_sold_info(self, partner):
        from checkout.models import CheckoutLine, Cart
        from intake.models import POLine
        sales = CheckoutLine.objects.filter(item__in=Item.objects.filter(product=self, partner=partner),
                                            cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED,
                                                              Cart.CANCELLED]).order_by("-cart__date_submitted")
        purchases = POLine.objects.filter(barcode=self.barcode, po__partner=partner).exclude(barcode=None).order_by(
            "-po__date")
        context = {}
        context["sales"] = sales
        context["x_sold"] = \
            sales.filter(cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED]).exclude(
                cancelled=True).aggregate(sum=Sum("quantity"))['sum']
        context["po_lines"] = purchases
        context["x_purchased"] = purchases.aggregate(sum=Sum("received_quantity"))['sum']
        context["inventory_log"] = InventoryLog.objects.filter(
            item__in=Item.objects.filter(product=self, partner=partner)).order_by("-timestamp")
        return context


class ItemQuerySet(PolymorphicQuerySet):

    def apply_generic_filters(self, partner_slug=None, price_low=Money(0, 'USD'), price_high=Money(float('inf'), 'USD'),
                              featured=None):
        items = self
        if partner_slug:
            items = items.filter(partner__slug=partner_slug)
        if featured:
            items = items.filter(featured=featured)
        if price_low > Money(0, 'USD'):
            items = items.filter(price__gte=price_low)
        if price_high < Money(float('inf'), 'USD'):
            items = items.filter(price__lte=price_high)
        return items

    def filter_preorder_or_secondary_release_date(self, manage=False, date=None):
        if date is None:
            date = datetime.now()
        return self.remove_drafts(manage).filter(product__preorder_or_secondary_release_date__isnull=False,
                                                 product__preorder_or_secondary_release_date__lte=date)

    def filter_release_date(self, manage=False, date=None):
        if date is None:
            date = datetime.now()
        return self.remove_drafts(manage).filter(product__release_date__isnull=False,
                                                 product__release_date__lte=date)

    def remove_drafts(self, manage=False):
        if not manage:
            return self.exclude(product__page_is_draft=True)
        return self

    def filter_visible(self, manage=False):
        preorder_date_items = self.filter_preorder_or_secondary_release_date(manage) \
            .filter(product__visible_on_preorder_secondary=True, override_visible=False)
        release_date_items = self.filter_release_date(manage) \
            .filter(product__visible_on_release=True, override_visible=False)
        items = preorder_date_items | release_date_items
        items = items.distinct() | self.filter_listed(manage) | self.filter_purchasable(manage)
        return items.distinct()

    def filter_listed(self, manage=False):
        preorder_date_items = self.filter_preorder_or_secondary_release_date(manage) \
            .filter(product__listed_on_preorder_secondary=True, override_listed=False)
        release_date_items = self.filter_release_date(manage) \
            .filter(product__listed_on_release=True, override_listed=False)
        items = preorder_date_items | release_date_items
        return items.distinct()

    def filter_purchasable(self, manage=False):
        """Shouldn't be needed I hope"""
        preorder_date_items = self.filter_preorder_or_secondary_release_date(manage) \
            .filter(product__purchasable_on_preorder_secondary=True, override_purchasable=False)
        release_date_items = self.filter_release_date(manage) \
            .filter(product__purchasable_on_release=True, override_purchasable=False)
        items = preorder_date_items | release_date_items
        return items.distinct()


class Item(RepresentationMixin, PolymorphicModel):
    objects = ItemQuerySet.as_manager()

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    DIGITAL = '1'
    INVENTORY = '2'
    MADE_TO_ORDER = '3'
    PRODUCT_TYPES = (
        (DIGITAL, "Digital"),
        (INVENTORY, "Inventory"),
        (MADE_TO_ORDER, "Made to Order")
    )
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT)
    page_visible = models.BooleanField(default=0)
    default_price = MoneyField(max_digits=19, decimal_places=2)  # This is used when setting sale prices.
    price = MoneyField(max_digits=19, decimal_places=2, default_currency='USD')
    enable_discounts = models.BooleanField(default=True)

    main_image = models.ForeignKey('ProductImage', on_delete=models.SET_NULL, blank=True, null=True)
    image_gallery = models.ManyToManyField('ProductImage', blank=True, related_name='item_images')
    featured = models.BooleanField(default=False)

    override_visible = models.BooleanField("Not Visible", default=False, help_text="overrides product settings")
    override_listed = models.BooleanField("Not Listed", default=False, help_text="overrides product settings")
    override_purchasable = models.BooleanField("Not Purchasable", default=False, help_text="overrides product settings")

    max_per_cart = None

    def __str__(self):
        return "{} ({} {})".format(self.product, self.get_type(), self.id)

    @property
    def listed(self):
        return not self.override_listed and self.product.listed

    # As property is the only one we can directly control at this level, its the only one we filter for
    @property
    def purchasable(self):
        return not self.override_purchasable and self.product.purchasable

    @property
    def visible(self):
        return not self.override_visible and self.product.visible

    def user_already_owns(self, user):
        return False

    def json(self, context={}):
        from .serializers import ItemSerializer
        return json.dumps(ItemSerializer(self, context).data)

    def to_react_representation(self, context={}):
        from .serializers import ItemSerializer
        return ItemSerializer(self, context=context).data

    def cart_owner_allowed_to_purchase(self, cart):
        return True

    def get_type(self):
        if isinstance(self, InventoryItem):
            return "InventoryItem"
        if isinstance(self, apps.get_model('digitalitems', 'DigitalItem')):
            return "DigitalItem"
        if isinstance(self, MadeToOrder):
            return "MadeToOrder"
        if isinstance(self, CustomChargeItem):
            return "Custom"

    def get_discount_price(self, user):
        if not self.enable_discounts:
            return self.price

        min_price = self.price
        return min_price

    BUTTON_STYLE_GOOD = 3
    BUTTON_STYLE_BACKORDER = 2
    BUTTON_STYLE_SOLD_OUT = 1

    def button_status(self, cart=None):
        """Returns a tuple of text and enable/disabled"""
        if self.purchasable:
            if self.product.is_preorder:
                return {'text': "Preorder", 'enabled': True, "style": self.BUTTON_STYLE_GOOD}
            else:
                return {'text': "Add to Cart", 'enabled': True, "style": self.BUTTON_STYLE_GOOD}
        else:
            return {'text': "Not Yet Available", 'enabled': False, "style": self.BUTTON_STYLE_SOLD_OUT}

    def purchase(self, cart):
        pass  # Most items do nothing when purchased


class InventoryItem(Item):
    use_linked_inventory = models.BooleanField(default=False)
    current_inventory = models.IntegerField(default=0)
    preallocated_inventory = models.IntegerField(default=0)
    allow_backorders = models.BooleanField(default=True)
    max_per_cart = models.IntegerField(null=True, blank=True, default=None)
    preallocated = models.BooleanField(default=False)
    allow_extra_preorders = models.BooleanField(default=False,
                                                help_text="If the item is preallocated and backorders are allowed, button will be backorder instead of marking as sold out of pre-orders")

    enable_restock_alert = models.BooleanField(default=False)
    low_inventory_alert_threshold = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        reason = kwargs.pop('change_reason', "Manual edit or Other")
        skip_log = kwargs.pop('skip_log', False)  # must pop kwargs before passing to regular constructor
        created_item = super(InventoryItem, self).save(*args, **kwargs)
        if not skip_log:  # handle log after item creation to ensure log can have a foreign key
            log_entry = self.inv_log.create(after_quantity=self.current_inventory, reason=reason)
            if self.preallocated and self.product.is_before_release:
                log_entry.after_preallocation_quantity = self.preallocated_inventory
                log_entry.save()
        return created_item

    def adjust_inventory(self, quantity, reason=None, line=None, purchase_order=None):
        """
        Adjusts current inventory and preallocated inventory
        @param quantity: amount to add, or subtract if negative.
        @param reason: Free text to be stored in the inventory log
        @param line: relevant cart line if sale
        @param purchase_order: relevant purchase order if intake
        @return: True, if inventory adjusted
        """

        # If this is a sale while preorders are live, we adjust preallocation amounts.
        is_preallocation_adjustment = (self.preallocated and self.product.is_before_release
                                       and quantity < 1)

        with transaction.atomic():
            ii = InventoryItem.objects.select_for_update().get(id=self.id)
            if line:
                if ii.inv_log.filter(line=line).exists():
                    return False  # If we already have a log of updating the inventory, quit
                    # This is how we prevent double submits affecting inventory twice.

            ii.current_inventory += quantity
            if ii.current_inventory <= 0:
                ii.current_inventory = 0
            # Create a new log entry
            log_entry = ii.inv_log.create(after_quantity=ii.current_inventory, change_quantity=quantity,
                                          reason=reason,
                                          line=line, po=purchase_order,
                                          is_preallocation_adjustment=is_preallocation_adjustment,
                                          )

            # Adjust preallocation amount
            if is_preallocation_adjustment:
                preallocation_change = quantity
                ii.preallocated_inventory += quantity
                if ii.preallocated_inventory <= 0:
                    ii.preallocated_inventory = 0
                log_entry.after_preallocation_quantity = ii.preallocated_inventory
                log_entry.change_preallocation_quantity = preallocation_change
                log_entry.save()

            ii.save(skip_log=True)

        self.refresh_from_db()
        return True

    def get_inventory(self):
        if self.preallocated and self.product.is_preorder:
            return self.preallocated_inventory
        return self.current_inventory

    def button_status(self, cart=None):
        """Returns a tuple of text, enable/disabled, and style
        :param cart:
        """
        inventory = self.get_inventory()
        if self.purchasable:
            if self.product.is_preorder:
                if not self.preallocated or (self.preallocated and inventory > 0):
                    return {'text': "Preorder", 'enabled': True, "style": self.BUTTON_STYLE_GOOD}
                elif self.preallocated and inventory <= 0:
                    if self.allow_extra_preorders and self.allow_backorders:
                        return {'text': "Backorder", 'enabled': True, "style": self.BUTTON_STYLE_BACKORDER}
                    else:
                        return {'text': "Pre-orders Sold Out", 'enabled': False,
                                "style": self.BUTTON_STYLE_SOLD_OUT}
            else:
                if inventory > 0:
                    return {'text': "Add to Cart", 'enabled': True, "style": self.BUTTON_STYLE_GOOD}
                elif self.allow_backorders:
                    return {'text': "Backorder", 'enabled': True, "style": self.BUTTON_STYLE_BACKORDER}
            return {'text': "Sold Out", 'enabled': False, "style": self.BUTTON_STYLE_SOLD_OUT}
        else:
            return {'text': "Not Yet Available", 'enabled': False,
                    "style": self.BUTTON_STYLE_SOLD_OUT}

    SECOND_WAVE_PREORDER = "Initial release pre-orders are sold out. Backorders of this product will arrive some time after release."
    BACKORDER_DISCLAIMER = "This item is not currently in stock. Place a backorder to receive the item when it returns to stock. Your entire order will be held until all items on your order are ready-to-ship."


class InventoryLog(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='inv_log')
    timestamp = models.DateTimeField(blank=True)
    is_preallocation_adjustment = models.BooleanField(default=False)  # If this was a sale during preallocation
    reason = models.CharField(max_length=200, blank=True, null=True)
    after_quantity = models.IntegerField(null=True)  # null values only from before the log was implemented.
    after_preallocation_quantity = models.IntegerField(null=True)
    change_quantity = models.IntegerField(default=0)
    change_preallocation_quantity = models.IntegerField(null=True)
    line = models.ForeignKey("checkout.CheckoutLine", on_delete=models.CASCADE, null=True, blank=True)
    po = models.ForeignKey("intake.PurchaseOrder", on_delete=models.CASCADE, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.timestamp:
            self.timestamp = timezone.now()
        return super(InventoryLog, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.item.product.name} adjusted at {self.timestamp}"


class MadeToOrder(Item):
    needs_quote = models.BooleanField(default=False)
    digital_purchase_necessary = models.BooleanField(default=False)
    # ^ Have to purchase the digital files to order a print
    current_inventory = models.IntegerField(default=0)

    approx_lead = models.DurationField(blank=True, null=True)

    external_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return str(self.id) + str(self.product)

    def digital_purchased(self, user):
        try:
            from digitalitems.models import DigitalItem
            item = self.product.item_set.instance_of(apps.get_model('digitalitems', 'DigitalItem')).get()
            return item.user_already_owns(user=user)
        except Exception as e:
            print(e)
            return False

    def get_inventory(self):
        return self.current_inventory

    def button_status(self, cart=None):
        status = super().button_status(cart)
        if status['style'] == self.BUTTON_STYLE_GOOD and self.current_inventory < 1:  # If not in stock change the style
            status['style'] = self.BUTTON_STYLE_BACKORDER
            status['text'] = "Made to Order"
        return status


class CustomChargeItem(Item):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    description = models.TextField()

    def notify_user_of_custom_charge(self, cart):
        if self.user:
            context = {'order': cart}
            html_template = get_template('shop/email/invoice_added_to_cart.html')
            msg = EmailMessage(subject='Invoice added to cart',
                               body=html_template.render(context),
                               from_email=None,
                               to=[self.user.email])
            msg.content_subtype = 'html'
            msg.send()


# class ComicItem(Item):
#     current_inventory = models.IntegerField(default=0)
#
#     def __str__(self):
#         return str(self.id) + str(self.product)
#
#
# class CardItem(Item):
#     condition = models.ForeignKey(CardCondition, on_delete=models.CASCADE)
#     current_inventory = models.IntegerField(default=0)
#
#     def __str__(self):
#         return str(self.id) + str(self.product)


class UsedItem(Item):
    condition_description = models.CharField(max_length=2000)

    def __str__(self):
        return str(self.id) + str(self.product)


class ProductImage(models.Model):
    image = models.ImageField()
    alt_text = models.CharField(max_length=200, blank=True, null=True,
                                help_text="Used in screen readers for the visually impared. " +
                                          " Blank to default to filename")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, blank=True, null=True)

    migrated_to = models.OneToOneField('images.Image', on_delete=models.SET_NULL, blank=True, null=True,
                                       related_name='migrated_from')

    def __str__(self):
        return "{} image ({}) from {}".format(self.alt_text, self.id, self.partner)

    def save(self, *args, **kwargs):
        if not self.alt_text:
            # Set alt text to the filename, without the extension, and replace underscores with spaces
            self.alt_text = ".".join(self.image.name.split('.')[:-1]).replace('_', ' ')
        return super(ProductImage, self).save(*args, **kwargs)

    def migrate(self):
        image, created = Image.objects.get_or_create(migrated_from=self)
        image.alt_text = self.alt_text
        image.partner = self.partner
        image.save()
        self.migrated_to = image
        self.save()
        success = True
        try:
            image.image_src.save(self.image.name, self.image.file)
            image.save()
            success = True
        except FileNotPresent:
            image.delete()
            success = False
        return image, success


class ContainsProducts(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="contains")
    quantity = models.PositiveIntegerField()
    of = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="contained_in_product")
    exact = models.BooleanField(default=True)
    same_except_box = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)
