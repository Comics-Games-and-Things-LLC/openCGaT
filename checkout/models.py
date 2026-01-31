import datetime
import json
import urllib.parse
from decimal import Decimal

import requests
import stripe
from address.models import AddressField
from django.conf import settings
from django.conf.global_settings import AUTH_USER_MODEL
from django.contrib.sites.models import Site
from django.core import mail
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist, BadRequest
from django.core.mail import EmailMessage
from django.db import models, transaction
from django.db.models import F, Sum, Q
from django.template.loader import get_template
from django.utils import timezone
from django.utils.timezone import now
from django_react_templatetags.mixins import RepresentationMixin
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from phonenumber_field.modelfields import PhoneNumberField

from checkout.managers import OpenCartManager, SavedCartManager, SubmittedCartManager
from digitalitems.models import DigitalItem
from intake.models import POLine
from partner.models import Partner, PartnerTransaction
from realaddress.abstract_models import AbstractAddress
from shop.models import Item, InventoryItem


class BillingAddress(AbstractAddress):
    pass


class ShippingAddress(AbstractAddress):
    phone_number = PhoneNumberField(
        "Phone number", blank=True,
        help_text="In case we need to call you about your order")


class Cart(RepresentationMixin, models.Model):
    objects = models.Manager()

    open = OpenCartManager()
    saved = SavedCartManager()
    submitted = SubmittedCartManager()

    site = models.ForeignKey(Site, on_delete=models.PROTECT)

    lost_damaged_or_stolen = models.BooleanField(default=False)
    broken_down = models.BooleanField(default=False,
                                      help_text="Removed from inventory as it was used for something else")

    at_pos = models.BooleanField(default=False)
    store_initiated_charge = models.BooleanField(default=False)
    owner = models.ForeignKey(
        AUTH_USER_MODEL,
        null=True, blank=True,
        related_name='carts',
        on_delete=models.SET_NULL,
    )
    email = models.EmailField(null=True, blank=True)  # If no owner, use the email instead.

    discount_code = models.ForeignKey('discount_codes.DiscountCode', on_delete=models.SET_NULL, null=True, blank=True)

    # cart statuses
    # - Frozen is for when a cart is in the checkout process and changes are not allowed.
    # - Processing is the point of no return when the user has clicked submit. This is to prevent rollback.
    OPEN, MERGED, SAVED, FROZEN, PROCESSING, SUBMITTED, PAID, COMPLETED, CANCELLED = (
        "Open", "Merged", "Saved", "Frozen", "Processing", "Submitted", "Paid", "Completed", "Cancelled")
    STATUS_CHOICES = (
        (OPEN, "Open - currently active"),
        (MERGED, "Merged - superseded by another cart"),
        (SAVED, "Saved - for items to be purchased later"),
        (FROZEN, "Frozen - the cart cannot be modified and is in checkout."),
        (PROCESSING, "Processing - the checkout process has begun and the cart is in limbo"),
        (SUBMITTED, "Submitted - has completed checkout process, but not paid"),
        (PAID, "Paid - user has paid"),
        (COMPLETED, "Complete - order has been delivered/picked up/etc"),
        (CANCELLED, "Cancelled - Order was cancelled")
    )
    SUBMITTED_STATUS_CHOICES = (
        (PROCESSING, "Processing - the checkout process has begun and the cart is in limbo"),
        (SUBMITTED, "Submitted - has completed being checked out"),
        (PAID, "Paid - user has paid"),
        (COMPLETED, "Complete - order has been delivered/picked up/etc"),
        (CANCELLED, "Cancelled - Order was cancelled")
    )

    status = models.CharField(
        "Status", max_length=128, default=OPEN, choices=STATUS_CHOICES)

    merge_target = models.ForeignKey('Cart', on_delete=models.SET_NULL, blank=True, null=True)

    date_created = models.DateTimeField("Date created", auto_now_add=True)
    date_merged = models.DateTimeField("Date merged", null=True, blank=True)
    date_processing = models.DateTimeField("Date processing started", null=True, blank=True)
    date_submitted = models.DateTimeField("Date submitted", null=True,
                                          blank=True)
    date_paid = models.DateTimeField("Date paid", null=True, blank=True)

    # Only if a cart is in one of these statuses can it be edited
    editable_statuses = (OPEN, SAVED)

    DIGITAL_ONLY, SHIP_ALL, PICKUP_ALL, PICKUP_ONE, MIXED = (
        "Digital Only", "Ship All", "Pickup All", "Pickup One", "Mixed")
    DELIVERY_CHOICES = (
        (PICKUP_ALL, "Pickup all items in this order"),
        (SHIP_ALL, "Ship all items in this order"),
        # (PICKUP_ONE, "Pickup items from a specific store, and ship the rest"),
        # (MIXED, "Change delivery method on a per-item basis"),
    )
    delivery_method = models.CharField(
        "delivery", max_length=128, null=True, default=None, blank=True, choices=DELIVERY_CHOICES)

    UPS, USPS, FEDEX, DHL = (
        "UPS", "USPS", "FEDEX", "DHL"
    )
    CARRIER_CHOICES = (
        (USPS, USPS),
        (UPS, UPS),
        (FEDEX, FEDEX),
        (DHL, DHL),
    )
    carrier = models.CharField(
        "delivery", max_length=20, null=True, default=None, blank=True, choices=CARRIER_CHOICES)

    PAY_IN_STORE, PAY_STRIPE = (
        "Pay in store", "Pay via Stripe"
    )
    PAYMENT_CHOICES = (
        (PAY_STRIPE, "Pay online via Credit or Debit Card"),
        (PAY_IN_STORE, "Pay in person at the following store:")
    )

    payment_method = models.CharField(
        "payment", max_length=128, null=True, default=None, blank=True, choices=PAYMENT_CHOICES)

    delivery_name = models.CharField(max_length=200, null=True, blank=True)
    delivery_apartment = models.CharField(max_length=20, null=True, blank=True)
    delivery_address = AddressField(null=True, related_name="delivery_address", blank=True)

    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.PROTECT, blank=True, null=True)
    billing_address = models.ForeignKey(BillingAddress, on_delete=models.PROTECT, blank=True, null=True)

    old_billing_address = AddressField(null=True, related_name="billing_address", blank=True)

    pickup_partner = models.ForeignKey(Partner, related_name="pickup_partner", null=True, on_delete=models.CASCADE,
                                       blank=True)
    payment_partner = models.ForeignKey(Partner, related_name="payment_partner", null=True, on_delete=models.CASCADE,
                                        blank=True)
    as_guest = models.BooleanField(null=True, default=None)

    final_total = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')
    final_tax = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')
    final_ship = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')

    cart_tax_rate = models.FloatField(help_text="Percent in decimal form( ex .055)", blank=True,
                                      null=True)  # Assumes all items have the same tax rate

    final_digital_tax = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')
    final_physical_tax = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')

    cash_paid = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')
    total_paid = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')

    amount_refunded = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')

    partner_transactions = models.ManyToManyField(PartnerTransaction, blank=True)

    set_in_taxjar = models.BooleanField(default=False)

    tracking_number = models.CharField(max_length=40, blank=True, null=True)
    ready_for_pickup = models.BooleanField(default=False)

    postage_paid = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')

    expense_not_sale = models.BooleanField(default=False)

    public_comments = models.TextField(blank=True, null=True)
    private_comments = models.TextField(blank=True, null=True)

    tax_error = models.TextField(blank=True, null=True)
    address_error = models.JSONField(blank=True, null=True)

    discount_code_message = models.TextField(null=True, blank=True)

    invoice_been_printed = models.BooleanField(default=False)

    def __str__(self):
        return "{} cart (id: {}, owner: {}, items: {}, total:{})".format(
            self.status, self.id, self.owner, self.num_items, self.final_total)

    # ============
    # Manipulation
    # ============

    def flush(self):
        """
        Remove all lines from cart.
        """
        if self.status == self.FROZEN:
            raise PermissionDenied("A frozen cart cannot be flushed")
        self.lines.all().delete()
        self._lines = None

    def update_quantity(self, item_id=None, line=None, quantity=1):
        if self.is_frozen:
            self.thaw()
        if line is None and item_id is None:
            raise Exception("need item or line")
        try:
            if line is None:
                line = self.lines.get(item_id=item_id)
            if line.item.max_per_cart is not None:
                if quantity > line.item.max_per_cart:
                    quantity = line.item.max_per_cart
            line.quantity = quantity
            if line.quantity == 0:
                line.delete()
            else:
                line.save()
            return True
        except CheckoutLine.DoesNotExist:
            return None
        except Exception as e:
            return False

    def add_item(self, item, quantity=1):
        """
        Add an item to the cart
        Returns (line, created).
          line: the matching cart line
          created: whether the line was created or updated
        """
        print(self, self.id, item, quantity)
        if item is None:
            raise Item.DoesNotExist
        print(hasattr(item, 'cart_owner_allowed_to_purchase'))
        if hasattr(item, 'cart_owner_allowed_to_purchase') and not item.cart_owner_allowed_to_purchase(self):
            raise PermissionDenied

        if quantity == 0:
            raise BadRequest

        if self.is_frozen:
            self.thaw()

        if not self.id:
            self.save()
            print("Saved cart to get an ID")
        new_quantity = quantity

        line, created = self.lines.get_or_create(item=item, submitted_in_cart__isnull=True)
        if not created:
            new_quantity = max(0, line.quantity + quantity)

            if item.max_per_cart is not None:
                if new_quantity > item.max_per_cart:
                    new_quantity = item.max_per_cart

        if not created:
            self.update_quantity(line=line, quantity=new_quantity)

        line.quantity = new_quantity
        line.save()
        if self.is_submitted:
            line.submit()
            self.update_final_totals()
        print(line, created)
        return line, created

    add = add_item

    def remove_from_cart(self, item_id):
        if self.is_frozen:
            self.thaw()

        if not self.id:
            self.save()
        try:
            self.lines.filter(item_id=item_id).delete()
            for line in self.lines.all():
                if not line.item.cart_owner_allowed_to_purchase(self):
                    line.delete()  # Remove all items the user isn't allowed to purchase after this item is removed
            return True
        except CheckoutLine.DoesNotExist:
            return None
        except Exception as e:
            return False

    def merge_line(self, line, add_quantities=True):
        """
        For transferring a line from one cart to this one.
        """
        try:
            existing_line = self.lines.get(item=line.item)
        except ObjectDoesNotExist:
            # Line does not already exist - reassign its cart
            line.cart = self
            line.save()
        else:
            # Line already exists - assume the max quantity is correct and
            # delete the old
            if add_quantities:
                existing_line.quantity += line.quantity
            else:
                existing_line.quantity = max(existing_line.quantity,
                                             line.quantity)
            self.update_quantity(line=existing_line, quantity=existing_line.quantity)  # Force max item check
            existing_line.save()
            line.delete()

    @property
    def text_summary(self):
        text = str(self)
        if self.discount_code:
            text += "\n\tWith Code: " + str(self.discount_code)
        for line in self.lines.all():
            text += "\n\t" + str(line.simple_string_summary)
        return text

    def merge(self, cart2, add_quantities=True):
        """
        Merges another cart with this one.
        cart2: The cart to merge into this one.
        add_quantities: Whether to add line quantities when they are merged.
        """
        print("Attempting to merge Carts")
        before_state_1 = self.text_summary
        before_state_2 = cart2.text_summary
        if cart2.payments.filter(collected=True):
            cart2.mark_processing()  # Mark the cart as processing, since this cart should not be open.
            # This may still miss carts if the payment status rolls back
        if cart2.is_submitted or cart2.is_processing:
            return  # Do not allow a processing cart to merge.
        for line_to_merge in cart2.lines.all():
            self.merge_line(line_to_merge, add_quantities)
        cart2.status = self.MERGED
        cart2.merge_target = self  # store what cart merged into this one, for future debugging purposes.
        cart2.date_merged = now()
        cart2.lines.all().delete()
        cart2.save()

        # Favor cart 2's discount code over cart 1's
        if cart2.discount_code:
            cart2.discount_code.validate_code_for_cart(self)
            self.save()

        after_state = self.text_summary
        email = EmailMessage("Merged Cart Debug Information",
                             f"""
We merged two carts. Double check that the cart merge was correct.
Cart 1 initial state:
{before_state_1}

Cart 2 initial state:
{before_state_2}

Final state: 
{after_state}
""",
                             to=[settings.EMAIL_HOST_USER])
        email.send()

    def freeze(self):
        """
        Freezes the cart so it cannot be modified.
        """
        if self.discount_code:
            self.discount_code.validate_code_for_cart(self)
        if not self.lines.exists():
            return
        self.status = self.FROZEN
        for line in self.lines.all():
            if not line.item.cart_owner_allowed_to_purchase(self):
                line.delete()  # Remove all items the user isn't allowed to purchase
        # TODO: consider displaying a message to the user that the item(s) were removed
        if not self.lines.exists():
            self.thaw()
        self.save()

    def thaw(self):
        """
        Unfreezes a cart so it can be modified again.
        Also resets the checkout process for this cart.
        """
        # First check to see if this cart has any completed payments:
        if self.payments.filter(collected=True):
            self.mark_processing()  # Mark the cart as processing, since this cart should not be open.
            raise Exception("Cannot thaw cart that is in progress")  # Do not re-open carts that have been paid for.

        self.delivery_method = None
        self.delivery_name = None
        self.delivery_apartment = None
        self.delivery_address = None
        self.shipping_address = None
        self.billing_address = None

        self.payment_method = None
        self.pickup_partner = None
        self.as_guest = None
        self.payment_partner = None

        self.final_total = None
        self.final_ship = None
        self.final_tax = None

        for pi in self.stripepaymentintent_set.filter(cancelled=False):
            pi.cancel()

        self.status = self.OPEN
        self.save()

    def mark_processing(self):
        """
        Mark the cart as processing
        """
        with transaction.atomic():  # First, set the cart as processing so it cannot roll back to frozen
            cart = Cart.objects.select_for_update().get(id=self.id)
            if cart.is_submitted or cart.status == self.PROCESSING:
                return  # don't resubmit a cart that is already processing.
            cart.status = self.PROCESSING
            cart.date_processing = now()
            cart.save()

    def submit(self):
        """
        Mark this cart as submitted
        """

        self.mark_processing()
        with transaction.atomic():
            cart = Cart.objects.select_for_update().get(id=self.id)
            if cart.is_submitted:
                return  # Can't resubmit a submitted cart
            for line in cart.lines.all():  # Must be done before setting status to submitted
                line.submit()
            cart.status = cart.SUBMITTED
            cart.date_submitted = now()
            if cart.payment_method != cart.PAY_IN_STORE:
                cart.payment_partner = None
            if cart.delivery_method != cart.PICKUP_ALL:
                cart.pickup_partner = None
            if cart.final_tax is None:
                cart.final_tax = cart.get_tax(final=True)
            if cart.final_ship is None:
                cart.final_ship = cart.get_shipping()
            if cart.final_total is None:
                cart.final_total = cart.get_final_less_tax() + cart.final_tax
                cart.total_paid = Money(0, "USD")
                cart.cash_paid = Money(0, "USD")
            cart.save()
        self.refresh_from_db()
        if self.is_submitted:
            self.send_submitted_email()
            partners, count = self.get_order_partners()
            for partner in partners:
                self.send_partner_submitted_email(partner)

    def update_final_totals(self):
        self.final_tax = self.get_tax(final=True)
        self.final_ship = self.get_shipping()
        self.final_total = self.get_final_less_tax() + self.final_tax
        self.save()

    def cancel(self):
        if not self.is_cancelled and self.status != "Completed":
            self.status = Cart.CANCELLED
            self.save()
            for pt in self.partner_transactions.all():
                pt.cancel()
            self.send_cancelled_email()

    def mark_completed(self):
        if self.status == Cart.PAID:
            self.status = Cart.COMPLETED
            for line in self.lines.all():
                line.complete()
            self.save()
            return True
        return False

    def pay_amount(self, amount, cash=False, timestamp=None):
        success = False
        if self.is_paid or self.status == self.CANCELLED:
            return True  # Don't pay for an already paid cart
        if not self.is_submitted:
            self.submit()  # if cart hasn't been submitted then submit. Has own atomic lock.
        with transaction.atomic():
            cart = Cart.objects.select_for_update().get(id=self.id)
            if cart.is_paid or cart.status == cart.CANCELLED:
                return  # Don't pay for an already paid cart

            if not isinstance(amount, Money):
                amount = Money(amount, "USD")

            if not cart.is_submitted:
                cart.submit()  # if cart isn't submitted yet submit
            if cart.total_paid is None:
                cart.total_paid = amount
            else:
                cart.total_paid += amount
            if cash:
                if cart.cash_paid is None:
                    cart.cash_paid = amount
                else:
                    cart.cash_paid += amount
            cart.save()
            success = True
            print("{} of {} paid on cart {}".format(cart.total_paid, cart.final_total, cart))
        self.refresh_from_db()
        if self.total_paid and self.total_paid + Money(.01, "USD") >= self.final_total:
            self.pay(timestamp=timestamp)
        return success

    def is_free(self):
        total = self.get_total_subtotal()
        return total.amount == 0

    def pay(self, method=None, timestamp=None, transaction_type=PartnerTransaction.PURCHASE):
        if not self.is_submitted:
            self.submit()  # if cart isn't submitted yet submit (has its own atomic lock)
        with transaction.atomic():
            cart = Cart.objects.select_for_update().get(id=self.id)
            if cart.is_paid or cart.status == cart.CANCELLED:
                return  # Don't pay for an already paid cart
            if method:
                cart.payment_method = method
            if timestamp is None:
                cart.date_paid = timezone.now()
            else:
                cart.date_paid = timestamp
            # Ensure cart is submitted at checkout.
            if not cart.is_submitted:
                cart.submit()  # if cart isn't submitted yet submit
            cart.status = cart.PAID
            print("Marking cart {} as paid".format(cart))
            cart.create_purchases()
            if not cart.is_shipping_required():
                cart.status = cart.COMPLETED
            cart.save()
        self.refresh_from_db()
        if self.is_paid:
            self.send_payment_email()
            try:
                self.pay_partners(transaction_type=transaction_type)
            except Exception as e:
                print(e)

    def is_shipping_required(self):
        """
        Test whether the cart contains physical items that require
        shipping.
        """
        if len(Item.objects.filter(id__in=self.lines.values('item_id')).not_instance_of(
                DigitalItem)) > 0:
            # If there are non-digital items then it must need shipped (or in-store pickup)
            return True
        return False

    def is_shipping_set(self):
        if self.is_shipping_required():
            if self.delivery_method == self.SHIP_ALL:  # If shipping anything we need a delivery address
                return self.shipping_address is not None
            elif self.delivery_method == self.PICKUP_ALL or self.delivery_method == self.PICKUP_ONE:
                # picking up anything we need a pickup partner address
                return self.pickup_partner is not None
            elif self.delivery_method == self.MIXED:
                # TODO: Check each item to ensure it has either delivery or pickup partner set
                # If any have delivery set ensure address set.
                return False
            return False
        return True

    @property
    def not_only_digital(self):
        items = Item.objects.filter(id__in=self.lines.values('item_id'))
        return items.not_instance_of(DigitalItem).exists()

    def is_account_required(self):
        items = Item.objects.filter(id__in=self.lines.values('item_id'))
        if items.instance_of(DigitalItem).exists():
            # If there are digital items or pack items
            # then the user must have an account
            return True
        return False

    def is_account_set(self):
        if self.owner:
            return True
        if not self.is_account_required() and self.email:
            return True
        return False

    def is_payment_required(self):
        for line in self.lines.all():
            if line.item.price.amount != 0:
                return True
        return False

    def is_billing_addr_required(self):
        if self.pickup_partner or self.payment_partner:
            return False
        if self.shipping_address:
            return False
        return True

    def is_delivery_method_set(self):
        """
        :return: true if there is a billing address or a pickup or shipping address
        """
        return (self.billing_address and not self.is_shipping_required()) or \
            (self.pickup_partner or self.shipping_address)

    def is_payment_method_set(self):
        """
        :return: True if there is a selected payment method
        """
        if self.payment_method is not None:
            return True
        return False

    def is_payment_set(self):
        """

        :return: True if we have a confirmed form of payment (includes stripe attempt)
        """
        if self.payment_method == self.PAY_STRIPE:
            return len(self.stripepaymentintent_set.filter(cancelled=False)) > 0
        elif self.payment_method == self.PAY_IN_STORE:
            return self.payment_partner is not None
        return False

    V_START = 'checkout_start'
    V_LOGIN = 'checkout_login'
    V_DELIVERY_METHOD = 'checkout_delivery_method'
    V_SHIPPING_ADDR = 'checkout_shipping_address'
    V_PAYMENT_METHOD = 'checkout_payment_method'
    V_BILLING_ADDRESS = 'checkout_billing_address'
    V_PAY_IN_STORE = 'checkout_pay_in_store'
    V_PAY_ONLINE = 'checkout_pay_online'
    V_DONE = 'checkout_done'

    # keep in sync with ts_src/checkout/components/CheckoutStep.tsx
    STEP_START = 0
    STEP_LOGIN = 1
    STEP_DELIVERY_METHOD = 2
    STEP_PAYMENT_COLLECTION = 3

    def completed_steps(self):
        steps = []
        if self.is_frozen:
            steps.append(self.STEP_START)
        if self.is_account_set():
            steps.append(self.STEP_LOGIN)
        if self.is_delivery_method_set():
            steps.append(self.STEP_DELIVERY_METHOD)
        return steps

    def ready_steps(self):
        steps = [self.STEP_START]
        if self.is_frozen:
            steps.append(self.STEP_LOGIN)
            if self.is_account_set():
                steps.append(self.STEP_DELIVERY_METHOD)
                if self.is_delivery_method_set():
                    steps.append(self.STEP_PAYMENT_COLLECTION)
        return steps

    def next_checkout_view(self, view=V_START, user=None):
        """
        This function returns the next view in the checkout process based on the current view and the user
        :param view:
        :param user:
        :return: The next view the user needs to see in the checkout process.
        """
        if not self.is_account_set():
            return self.V_LOGIN
        if view is self.V_START:
            if self.is_shipping_required():
                return self.V_DELIVERY_METHOD
            if self.is_payment_required():
                return self.V_PAYMENT_METHOD
        elif view is self.V_LOGIN:
            if self.is_shipping_required():
                return self.V_DELIVERY_METHOD
            if self.is_payment_required():
                return self.V_PAYMENT_METHOD
            return self.V_DONE
        elif view is self.V_DELIVERY_METHOD:
            if self.is_shipping_required() and self.delivery_method != self.PICKUP_ALL:
                return self.V_SHIPPING_ADDR
            if self.is_payment_required():
                return self.V_PAYMENT_METHOD
        elif view is self.V_SHIPPING_ADDR:
            if self.tax_error:
                return self.V_SHIPPING_ADDR
            return self.V_PAYMENT_METHOD
        elif view is self.V_PAYMENT_METHOD:
            if self.is_billing_addr_required():
                return self.V_BILLING_ADDRESS
            elif self.payment_method == self.PAY_IN_STORE:
                return self.V_DONE
            else:
                return self.V_PAY_ONLINE
        elif view is self.V_BILLING_ADDRESS:
            if self.tax_error:
                return self.V_BILLING_ADDRESS
            return self.V_PAY_ONLINE
        return self.V_DONE

    # ==========
    # Properties
    # ==========

    @property
    def is_empty(self):
        """
        Test if this cart is empty
        """
        return self.id is None or self.num_lines == 0

    @property
    def num_lines(self):
        """Return number of lines"""
        return self.lines.all().count()

    @property
    def num_items(self):
        """Return number of items"""
        if self.id is not None:
            return self.lines.aggregate(sum=Sum("quantity"))['sum']
        return 0

    @property
    def num_active_items(self):
        """Return number of items that are not cancelled"""
        if self.id is not None:
            return self.lines.filter(cancelled=False).aggregate(sum=Sum("quantity"))['sum']
        return 0

    @property
    def num_ready_items(self):
        """Return number of items that are ready or complete"""
        if self.id is not None:
            return self.lines.filter(Q(ready=True, fulfilled=False) | Q(fulfilled=True)).aggregate(sum=Sum("quantity"))[
                'sum']
        return 0

    def get_other_items_for_customer(self, paid_only=False):
        if not self.owner:
            return None
        return other_items_for_customer(self.owner, cart=self, paid_only=paid_only)

    @property
    def time_before_submit(self):
        if not self.date_submitted:
            return None
        return self.date_submitted - self.date_created

    @property
    def time_since_creation(self, test_datetime=None):
        if not test_datetime:
            test_datetime = now()
        return test_datetime - self.date_created

    @property
    def is_submitted(self):  # Purposefully excluding the "processing" status here
        return self.status in [self.SUBMITTED, self.PAID, self.COMPLETED, self.CANCELLED]

    @property
    def is_cancelled(self):
        return self.status == self.CANCELLED

    @property
    def is_frozen(self):
        return self.status == self.FROZEN

    @property
    def is_processing(self):
        return self.status == self.PROCESSING

    @property
    def can_be_edited(self):
        """
        Test if a cart can be edited
        """
        return self.status in self.editable_statuses

    @property
    def is_paid(self):
        return self.status in [self.PAID, self.COMPLETED]

    @property
    def can_ship(self):
        return not self.in_store_pickup_only

    @property
    def in_store_pickup_only(self):
        return self.lines.filter(item__product__in_store_pickup_only=True).exists()

    # =============
    # Query methods
    # =============

    def get_total_subtotal(self) -> Money:
        total = Money(0, "USD")
        for line in self.lines.prefetch_related('item', 'item__product').all():
            total += line.get_subtotal()
        return total

    def get_subtotal_after_cancellations(self) -> Money:
        total = Money(0, "USD")
        if self.status == Cart.CANCELLED:
            return total
        for line in self.lines.filter(cancelled=False):
            total += line.get_subtotal()
        return total

    def get_estimated_total(self):
        return self.get_total_subtotal() + self.get_tax()

    @property
    def final_subtotal_no_shipping(self) -> Money:
        return (handle_null_money(self.final_total)
                - handle_null_money(self.final_ship)
                - handle_null_money(self.final_tax))

    @property
    def final_tax_percentage(self) -> Decimal:
        if not self.final_subtotal_no_shipping:
            return Decimal(0)
        return handle_null_money(self.final_tax) / self.final_subtotal_no_shipping

    def get_cancelled_amount(self) -> Decimal:
        if self.status == Cart.CANCELLED:
            return self.final_total.amount
        total = Money(0, "USD")
        for line in self.lines.filter(cancelled=True):
            total += line.get_subtotal()

        return total.amount * (1 + self.final_tax_percentage)

    def get_refunded_amount(self) -> Money:
        amount = Money(0, "USD")
        if self.amount_refunded:
            amount = self.amount_refunded
        for payment in self.payments.all():
            amount += payment.get_refunded_amount()
        return amount

    def get_pre_discount_subtotal(self):
        return Money(self.lines.aggregate(sum=Sum(F('item__price') * F('quantity')))["sum"], "USD")

    def get_digital_total(self):
        total = Money(0, "USD")
        for line in self.lines.all():
            if isinstance(line.item, DigitalItem):
                total += line.get_subtotal()
        return total

    def get_physical_total(self):
        total = Money(0, "USD")
        for line in self.lines.all():
            if not isinstance(line.item, DigitalItem):
                total += line.get_subtotal()
        return total

    def get_shipping(self):
        """
        This function gets the cost of shipping
        :return: 4, 0 if not required.
        """
        if self.is_shipping_required():
            if self.delivery_method == self.SHIP_ALL:
                return Money(4, "USD")
        return Money(0, "USD")

    def can_get_shipping(self):
        """
        Checks to see if we can get shipping
        :return:
        """
        if self.delivery_method == self.SHIP_ALL:
            if self.delivery_address:
                return True
        else:
            return False

    def get_approx_transac_fees(self):
        subtotal = self.get_total_subtotal()
        return Money(subtotal.amount * Decimal('0.029') + Decimal('.50'), "USD")

    def can_get_tax(self):
        tax_addr = self.get_tax_address()
        if tax_addr is None:
            return False
        return True

    def get_tax_address(self):
        '''
        This function returns the address used for calculating tax on the order.
            If paid in store we use the partner's address.
            If the order is being picked up, we use the partner's address.
            If the order is being shipped we use the shipping address,
             and then fall back to billing address,
            then shipping address if that was null
        Checkout v2 doesn't differentiate between shipping and billing addresses anymore,
            and only uses the shipping address field.
        Clear this up once checkout v1 is retired. This logic is duplicated somewhat in get_tax,
            since we just use the in_store tax rate there.
        :return: an address, or None
        '''
        if self.payment_method == self.PAY_IN_STORE:
            if self.payment_partner is not None:
                return self.payment_partner.address
        elif self.is_shipping_required():
            if self.delivery_method == self.PICKUP_ALL:
                if self.pickup_partner is not None:
                    return self.pickup_partner.address
            elif self.delivery_method == self.SHIP_ALL:
                if self.shipping_address is not None:
                    return self.shipping_address
        if self.billing_address is not None:
            return self.billing_address
        else:
            return self.shipping_address

    def get_tax(self, final=False):
        try:
            subtotal = self.get_total_subtotal()
            if self.payment_method == self.PAY_IN_STORE and self.payment_partner is not None:
                rate = self.payment_partner.in_store_tax_rate
            elif self.delivery_method == self.PICKUP_ALL and self.pickup_partner is not None:
                rate = self.pickup_partner.in_store_tax_rate
            else:
                address = self.get_tax_address()
                if address is None:
                    return Money(0, "USD")
                rate = TaxRateCache.taxes.get_tax_rate(address)

            tax = subtotal * rate
            self.cart_tax_rate = rate
            if final:
                self.final_tax = tax
            self.tax_error = False
            self.save()
            return tax

        except Exception as e:
            print(e)
            print("\n")
            self.tax_error = True
            self.save()
            mail.mail_admins("Tax rate calculation for cart {} failed".format(self.id), fail_silently=True,
                             message=str(e))
            return Money(0, 'USD')

    def get_estimate_total(self):
        return self.get_total_subtotal() + self.get_tax(final=False) + self.get_shipping()

    def get_final_less_tax(self):
        return self.get_total_subtotal() + self.get_shipping()

    def get_disclaimer_text(self):
        has_backorders = self.lines.filter(quantity__gt=F('item__inventoryitem__current_inventory'),
                                           item__product__release_date__lt=datetime.datetime.now()
                                           ).exists()

        preorders = self.lines.filter(item__product__release_date__gte=datetime.datetime.now())
        backorder_preorders_from_stock = preorders.filter(item__inventoryitem__preallocated=False,
                                                          quantity__gt=F(
                                                              'item__inventoryitem__current_inventory')
                                                          ).exists()
        backorder_preorders_from_preallocation = preorders.filter(item__inventoryitem__preallocated=True,
                                                                  quantity__gt=F(
                                                                      'item__inventoryitem__preallocated_inventory')
                                                                  ).exists()
        has_backorder_preorder = backorder_preorders_from_stock or backorder_preorders_from_preallocation
        text = ""
        if has_backorder_preorder:
            text = (text + "Initial release pre-orders of one or more items are sold out. " +
                    "Those products will arrive some time after release. ")
        if preorders.exists() or has_backorders or has_backorder_preorder:
            text = (text + "One or more items are not currently in stock. " +
                    "Your entire order will be held until all items on your order are ready-to-ship. ")

        print(text)
        return text.strip()

    def json(self):
        from .serializers import CartSerializer
        return json.dumps(CartSerializer(self).data)

    def id_json(self):
        return json.dumps({"id": self.id})

    def to_react_representation(self, context={}):
        from .serializers import CartSerializer
        if self.id:
            return CartSerializer(self).data
        return json.dumps({})

    def create_purchases(self):
        if self.is_paid:
            for line in self.lines.all():
                line.purchase()

    @property
    def single_partner(self):
        partners, count = self.get_order_partners()
        if count != 1:
            return False
        partner = partners.first()
        if self.pickup_partner and self.pickup_partner != partner:
            return False
        if self.payment_partner and self.payment_partner != partner:
            return False
        return True

    def get_pickup_partners(self):
        partner_id_list = Item.objects.filter(id__in=self.lines.values('item_id')).not_instance_of(
            DigitalItem).values_list('partner_id', flat=True).distinct()
        return Partner.objects.filter(id__in=partner_id_list)

    def get_order_partners(self):
        """
        Gets the number of partners with items in the order  #and the pickup or shipping partner if applicable.
        :return: list of partners, count of partners with non-free items (up to 2 less than total in list)
        """
        partner_id_list = self.lines.filter(price_per_unit_at_submit__gt=0,
                                            partner_at_time_of_submit__isnull=False).values_list(
            'partner_at_time_of_submit_id', flat=True).distinct()
        partner_list = Partner.objects.filter(id__in=partner_id_list)
        count = partner_list.count()
        # if self.payment_partner:
        #     partner_list |= Partner.objects.filter(id=self.payment_partner.id)
        # if self.pickup_partner:
        #     partner_list |= Partner.objects.filter(id=self.pickup_partner.id)
        return partner_list.distinct(), count

    def pay_partners(self, transaction_type=PartnerTransaction.PURCHASE, suppress_emails=False):
        if self.is_paid and not self.is_cancelled and self.partner_transactions.count() == 0:
            partners, count = self.get_order_partners()
            print("Paying cart {}'s {} partners: {}".format(self, count, partners))
            for partner in partners:
                self.pay_partner(partner, count, transaction_type)
                if not suppress_emails:
                    try:
                        self.send_partner_paid_email(partner)
                    except Exception as e:
                        print("Couldn't send email:")
                        print(e)

    def pay_partner(self, partner, number_of_partners, transaction_type=PartnerTransaction.PURCHASE):
        # for line in self.lines.filter(item_id__in=Item.objects.instance_of(MadeToOrder).values_list('item_id')):
        # pass  # TODO handle second partner on MTO items, royalties
        if not self.is_paid or partner is None:
            return  # Exit early if this cart has not been paid
        if not self.partner_transactions.filter(partner=partner).exists():
            partner_subtotal = Money(0, "USD")
            partner_fees = Money(0, "USD")

            for line in self.lines.filter(partner_at_time_of_submit=partner):
                line_subtotal = line.get_subtotal()
                partner_subtotal += line_subtotal
                partner_fees += (line_subtotal * (1 - partner.get_cut(line.item)))
            # if self.payment_partner == partner:
            #     # Paying in-store gives the paying store a chunk to handle transaction fees)
            #     partner_fees -= (self.get_total_subtotal() * float(.03)) + Money(.50, 'USD')

            # Take 3% for payment processing plus up to 50c divided by the total number of partners on the transaction.
            if partner_subtotal.amount != 0 and number_of_partners > 0:  # Ignore fee if item free, and for free orders
                partner_fees += (partner_subtotal * float(.03)) + (Money(.50, 'USD') / number_of_partners)
            pt = self.partner_transactions.create(partner=partner,
                                                  type=transaction_type,
                                                  transaction_total=self.final_total,
                                                  transaction_subtotal=partner_subtotal,
                                                  transaction_fees=partner_fees)
            if self.date_paid:
                pt.timestamp = self.date_paid
                pt.save()
            from billing.models import BillingEvent
            # Ensure billing event does not already exist
            if not BillingEvent.objects.filter(cart=self, partner=partner).exists():
                BillingEvent.objects.create(cart=self,
                                            partner=partner,
                                            type=BillingEvent.COLLECTED_FROM_CUSTOMER,
                                            platform_fee=partner_fees,
                                            subtotal=partner_subtotal,
                                            final_total=partner_subtotal - partner_fees,
                                            email_at_time_of_event=self.get_order_email(),
                                            user=self.owner,
                                            timestamp=self.date_paid
                                            )

    def clear_partner_payments(self):
        for pt in self.partner_transactions.all():
            pt.delete()

    def remove_partner_payment(self, partner):
        try:
            self.partner_transactions.get(partner=partner).delete()
        except Exception as e:
            print(e)

    def reset_partner_payment(self, partner):
        self.remove_partner_payment(partner)
        partners, count = self.get_order_partners()
        self.pay_partner(partner, count)

    def mark_shipped(self):
        try:
            self.send_shipping_email()
        except Exception:
            pass
        self.status = self.COMPLETED
        self.save()

    def mark_ready_for_pickup(self):
        try:
            self.send_ready_for_pickup_email()
        except Exception:
            pass
        self.ready_for_pickup = True

        self.save()

    def get_order_email(self):
        if self.owner and self.owner.email:
            return self.owner.email
        if self.email:
            return self.email

    def send_cancelled_email(self):
        if self.get_order_email():
            context = {'order': self}
            html_template = get_template('checkout/email/order_cancelled.html')
            msg = EmailMessage(subject='CG&T Order Cancelled #{}'.format(self.id),
                               body=html_template.render(context),
                               from_email=None,
                               to=[self.get_order_email()])
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)
        partners, _ = self.get_order_partners()
        for partner in partners:
            context = {'order': self}
            html_template = get_template('checkout/email/order_cancelled.html')
            msg = EmailMessage(subject='CG&T Order Cancelled #{}'.format(self.id),
                               body=html_template.render(context),
                               from_email=None,
                               bcc=list(partner.administrators.all().values_list("email", flat=True)))
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)

    def send_submitted_email(self):
        if self.get_order_email():
            context = {'order': self}
            html_template = get_template('checkout/email/submitted.html')
            msg = EmailMessage(subject='CG&T Order Submitted #{}'.format(self.id),
                               body=html_template.render(context),
                               from_email=None,
                               to=[self.get_order_email()])
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)

    def send_payment_email(self):
        if self.get_order_email():
            context = {'order': self}
            html_template = get_template('checkout/email/paid.html')
            msg = EmailMessage(subject='CG&T Order Paid #{}'.format(self.id),
                               body=html_template.render(context),
                               from_email=None,
                               to=[self.get_order_email()])
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)

    def send_shipping_email(self):
        if self.get_order_email():
            context = {'order': self}
            html_template = get_template('checkout/email/tracking_update.html')
            msg = EmailMessage(subject='CG&T Order Shipped #{}'.format(self.id),
                               body=html_template.render(context),
                               from_email=None,
                               to=[self.get_order_email()])
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)

    def send_ready_for_pickup_email(self):
        if self.get_order_email():
            context = {'order': self}
            html_template = get_template('checkout/email/ready_for_pickup.html')
            msg = EmailMessage(subject='CG&T Order Ready for Pickup #{}'.format(self.id),
                               body=html_template.render(context),
                               from_email=None,
                               to=[self.get_order_email()])
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)

    def send_status_update(self):
        if self.get_order_email():
            context = {'order': self}
            html_template = get_template('checkout/email/status_update.html')
            msg = EmailMessage(subject='CG&T Order #{} Status Update'.format(self.id),
                               body=html_template.render(context),
                               from_email=None,
                               to=[self.get_order_email()])
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)

    def send_partner_paid_email(self, partner):
        context = {'order': self,
                   'partner': partner}
        html_template = get_template('checkout/email/partner_paid.html')
        msg = EmailMessage(subject='CG&T Order Paid #{}'.format(self.id),
                           body=html_template.render(context),
                           from_email=None,
                           bcc=list(partner.administrators.all().values_list("email", flat=True)))
        msg.content_subtype = 'html'
        msg.send(fail_silently=True)

    def send_partner_submitted_email(self, partner):
        context = {'order': self,
                   'partner': partner}
        html_template = get_template('checkout/email/partner_submitted.html')
        msg = EmailMessage(subject='CG&T Order Submitted #{}'.format(self.id),
                           body=html_template.render(context),
                           from_email=None,
                           bcc=list(partner.administrators.all().values_list("email", flat=True)))
        msg.content_subtype = 'html'
        msg.send(fail_silently=True)

    def cancellable(self):
        for line in self.lines:
            if not line.cancellable():
                return False
        return True


class CheckoutLine(models.Model):
    item = models.ForeignKey('shop.Item', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField(default=1)

    cart = models.ForeignKey(Cart,
                             on_delete=models.PROTECT,
                             related_name='lines', blank=True, null=True)

    submitted_in_cart = models.ForeignKey(Cart, null=True, blank=True,
                                          on_delete=models.PROTECT,
                                          related_name='lines_submitted')

    date_added = models.DateTimeField(auto_now_add=True)

    @property
    def submitted(self):
        return self.submitted_in_cart is not None

    price_per_unit_at_submit = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True)
    price_per_unit_override = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True)
    partner_at_time_of_submit = models.ForeignKey(Partner, on_delete=models.PROTECT, null=True, blank=True)

    tax_per_unit = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True)
    name_of_item = models.TextField(null=True, blank=True)  # Name at submit (in case it changed)

    paid_in_cart = models.ForeignKey(Cart, null=True, blank=True,
                                     on_delete=models.PROTECT,
                                     related_name='lines_paid')

    @property
    def paid(self):
        return self.paid_in_cart is not None

    fulfilled_in_cart = models.ForeignKey(Cart, null=True, blank=True,
                                          on_delete=models.PROTECT,
                                          related_name='lines_fulfilled')

    fulfilled = models.BooleanField(default=False)
    fulfilled_timestamp = models.DateTimeField(null=True, blank=True)

    ready = models.BooleanField(default=False)
    ready_timestamp = models.DateTimeField(null=True, blank=True)

    cancelled = models.BooleanField(default=False)
    cancelled_timestamp = models.DateTimeField(null=True, blank=True)

    back_or_pre_order = models.BooleanField(default=False)  # If the quantity was zero at time of submit.
    is_preorder = models.BooleanField(default=False)  # If we were in the preorder window at the time of submit.
    inventory_at_time_of_submit = models.IntegerField(blank=True,
                                                      null=True)  # Quantity in stock at time of submit (DOES NOT INCLUDE PREALLOCATION)

    discount_code_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-date_added"]

    def __str__(self):
        return f"{self.cart} {self.simple_string_summary}"

    @property
    def simple_string_summary(self):
        name = self.name_of_item if self.submitted else self.item
        return f"Line {self.id}: {name} x {self.quantity}"

    @property
    def completely_in_stock_or_allocated(self):
        if isinstance(self.item, InventoryItem):
            return self.item.get_inventory() >= self.quantity
        else:
            return False

    @property
    def quantity_to_backorder(self):
        if isinstance(self.item, InventoryItem):
            if not self.completely_in_stock_or_allocated:
                return self.quantity - self.item.get_inventory()
            return 0

    @property
    def eligible_for_early_release(self):
        if self.cart.delivery_method != Cart.PICKUP_ALL:
            return False
        return self.item and self.item.product.in_store_early_release_date is not None

    @property
    def status_text(self):
        if isinstance(self.item, InventoryItem):
            if self.item.product.is_preorder:
                backorder_or_preorder = "preorder"
            else:
                backorder_or_preorder = "backorder"

            if self.cart.is_submitted:
                if self.cancelled or self.cart.status == Cart.CANCELLED:
                    return "Cancelled"
                if self.fulfilled or self.cart.status == Cart.COMPLETED:
                    if self.fulfilled_in_cart and self.fulfilled_in_cart != self.cart:
                        return "Fulfilled with order {}".format(self.fulfilled_in_cart.id)
                    return "Fulfilled"
                if self.ready or self.cart.ready_for_pickup:
                    delivery_method = "for pickup"
                    if self.cart.delivery_method == Cart.SHIP_ALL:
                        delivery_method = "to ship"
                    if not self.item or not self.item.product.is_preorder:
                        return "Ready {}".format(delivery_method)
                    release_date = self.item.product.release_date
                    if self.eligible_for_early_release:
                        release_date = self.item.product.in_store_early_release_date
                    return f"Ready {delivery_method} on {release_date}"
                if self.cart.status != Cart.COMPLETED and self.back_or_pre_order:
                    if self.is_preorder:
                        return "Preorder"
                    return backorder_or_preorder.title()  # make the first letter capital
                # Return the cart status if we don't have any line-specific overrides
                return self.cart.status
            else:
                if self.completely_in_stock_or_allocated:
                    if self.item.product.is_preorder:
                        return "Preorder"
                    return "In stock"
                else:
                    backorder = self.quantity_to_backorder
                    in_stock = self.quantity - backorder
                    if in_stock == 0:
                        return "{} will be {}ed".format(backorder, backorder_or_preorder)
                    else:
                        if self.item.product.is_preorder:
                            return "{} preallocated \n" \
                                   "{} will be {}ed".format(in_stock, backorder, backorder_or_preorder)
                        return "{} in stock \n" \
                               "{} will be {}ed".format(in_stock, backorder, backorder_or_preorder)

        else:
            return ""

    @transaction.atomic
    def split(self, second_quantity=1):
        """
        :param second_quantity: Defaults to 1. The quantity for the second line.
        :return: a new line or null
        """
        line = CheckoutLine.objects.get(id=self.id)
        if line.quantity > second_quantity:
            second_line = CheckoutLine.objects.get(id=self.id)
            second_line.id = None
            # Second line is now a copy of the inital line.
            second_line.quantity = second_quantity
            second_line.inventory_at_time_of_submit = None
            second_line.save()
            line.quantity -= second_quantity
            line.save()
            return second_line
        return None

    def get_price(self) -> Money:
        """
        Returns price at submit, or if cart open, returns price with discount code or patreon discount.
        :return: item price
        """
        if self.cart.is_submitted and self.price_per_unit_at_submit:
            return self.price_per_unit_at_submit
        else:
            if self.price_per_unit_override:
                if self.cart.discount_code and self.cart.discount_code.in_store_only:
                    (has_discount, new_price) = self.cart.discount_code.apply_discount_to_line_item(self)
                    if has_discount:
                        return new_price
                return Money(self.price_per_unit_override.amount, 'USD')
            if self.item is not None:
                if self.cart.discount_code:
                    (has_discount, new_price) = self.cart.discount_code.apply_discount_to_line_item(self)
                    if has_discount:
                        return new_price
                else:
                    if self.discount_code_message:
                        self.discount_code_message = None
                        self.save()
                return self.get_item_price()
            else:
                return Money(0, "USD")  # If item isn't present that's a big issue.

    def get_item_price(self) -> Money:
        """
        Get the price of the item (before calculating any discounts)
        Do not use except for in get_price
        :return:
        """
        if self.cart.at_pos and self.item.in_store_only_price:
            return self.item.in_store_only_price
        return self.item.price

    def get_proportional_tax(self):
        if self.cart.final_tax:
            final_tax = self.cart.final_tax.amount
            if self.cart.final_total.amount - final_tax <= 0:
                return Money(0, 'USD')
            proportion = self.get_subtotal().amount / (self.cart.final_total.amount - final_tax)
            return Money(final_tax * proportion, "USD")

        return Money(0, 'USD')

    def get_subtotal_with_tax(self):
        if self.cart.final_tax:
            return Money(self.get_proportional_tax().amount + self.get_subtotal().amount, 'USD')

    def get_subtotal(self) -> Money:
        return Money(self.get_price().amount * self.quantity, 'USD')

    def get_pre_discount_price(self):
        return self.item.default_price

    def get_pre_discount_subtotal(self):
        return self.get_pre_discount_price() * self.quantity

    def get_estimated_store_cost(self):
        if self.item is None or (self.item.product and self.item.product.barcode is None):
            return  # Quit if this product doesn't have a barcode
        po_lines = POLine.objects.filter(po__partner=self.item.partner,
                                         barcode=self.item.product.barcode,
                                         received_quantity__gte=1).order_by("po__date")
        # TODO: change this to remaining quantity
        if po_lines:
            return po_lines.first().actual_cost
        return None

    def submit(self):
        self.price_per_unit_at_submit = self.get_price()
        self.partner_at_time_of_submit = self.item.partner
        self.name_of_item = self.item.product.name
        if hasattr(self.item, 'description'):
            self.name_of_item += " " + self.item.description
        self.submitted_in_cart = self.cart
        self.reduce_inventory()
        self.save()

    def pay(self):
        """Only call pay if the cart has been paid"""
        self.paid_in_cart = self.cart

    def cancel(self):
        self.cancelled = True
        self.cancelled_timestamp = datetime.datetime.utcnow()

    def mark_ready(self):
        self.ready = True
        self.ready_timestamp = datetime.datetime.utcnow()

    def purchase(self):
        self.item.purchase(cart=self.cart)

    def complete(self):
        self.fulfilled = True
        self.fulfilled_timestamp = datetime.datetime.utcnow()

    def reduce_inventory(self):
        """
        Reduces inventory status and sets back_or_pre_order and "is_preorder"
        """
        if isinstance(self.item, InventoryItem):
            back_or_preorder = not self.completely_in_stock_or_allocated
            inventory_before_submit = self.item.current_inventory
            success = self.item.adjust_inventory(quantity=-self.quantity, reason="Sold in cart {}".format(self.cart_id),
                                                 line=self)
            if success:  # Prevent this from running again on duplicate submits.
                self.inventory_at_time_of_submit = inventory_before_submit
                self.back_or_pre_order = back_or_preorder
                if self.item.product.is_preorder:
                    self.is_preorder = True
                self.save()

    def cancellable(self):
        if isinstance(self.item, DigitalItem):
            if self.item.download_history.exists(user=self.cart.owner):
                return False
        return True

    def get_proportional_postage_paid(self) -> Money:
        if self.cart.postage_paid:
            return Money((self.cart.postage_paid.amount - self.cart.final_ship.amount) * (
                    self.get_subtotal() / self.cart.get_total_subtotal()), 'USD')
        return Money(0, "USD")


class UserDefaultAddress(models.Model):
    user = models.OneToOneField(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="default_address")
    address = AddressField()


class StripeCustomerIdManager(models.Manager):
    def get_customer_id(self, user):
        try:
            customer_id = user.stripe_id.id
        except StripeCustomerId.DoesNotExist:
            customer = stripe.Customer.create(email=user.email)
            customer_id = customer['id']
            StripeCustomerId.objects.create(user=user, id=customer_id)
        return customer_id


class StripeCustomerId(models.Model):
    user = models.OneToOneField(AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stripe_id")
    id = models.CharField(max_length=50, primary_key=True)
    objects = StripeCustomerIdManager()


class StripePaymentIntent(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True)
    for_subscription = models.BooleanField(default=False)
    amount_to_pay = MoneyField(max_digits=19, decimal_places=2, null=True, default_currency='USD')
    id = models.CharField(max_length=50, primary_key=True)
    cancelled = models.BooleanField(default=False)
    captured = models.BooleanField(default=False)

    def __str__(self):
        name = "Stripe Intent {} for {}".format(self.id, self.amount_to_pay)
        if self.captured:
            name += ", captured"
        return name

    @transaction.atomic
    def try_mark_captured(self):
        if not self.captured:
            intent = stripe.PaymentIntent.retrieve(self.id)
            cart = self.cart
            if intent.amount_received > 0:
                timestamp = intent.charges.data[0].created
                cart.pay_amount(Money(intent.amount_received / 100.0, "USD"),
                                timestamp=datetime.datetime.fromtimestamp(timestamp))
                self.captured = True
                self.save()

    def cancel(self):
        pi = stripe.PaymentIntent.retrieve(self.id)
        pi.cancel()
        self.cancelled = True
        self.save()

    def get_json(self):
        try:
            pi = stripe.PaymentIntent.retrieve(self.id)
            return pi
        except stripe.error.InvalidRequestError:
            return  # This prevents the system from breaking when viewing production data with the test API key


class TaxRateManager(models.Manager):
    def get_tax_rate(self, address):
        location = ""

        params = {'to_country': address.country.code}
        if address is None:
            raise Exception("Blank Address")
        if address.country is None:
            raise Exception("Missing Country")
        if address.line4:
            params['to_city'] = address.line4
            location += address.line4 + ", "
        if address.postcode:
            params['to_postal_code'] = address.postcode
            location += address.postcode + ", "
        location += address.country.code

        try:
            tax = super().get(location=location)
            if tax.rate is None:
                raise Exception("No tax rate stored")
            if tax.updated < timezone.now() - datetime.timedelta(weeks=12):
                raise Exception("Tax cache too old")
            return tax.rate
        except Exception as e:
            print(e)
            params = urllib.parse.urlencode(params)
            suffix = "tax_rates/calculate?{}".format(params)
            print("{}{}".format(settings.QUADERNO_URL, suffix))
            response = requests.get(
                "{}{}".format(settings.QUADERNO_URL, suffix),
                auth=(settings.QUADERNO_PRIVATE, "x"),
                headers={
                    'User-Agent': "CG&T",
                }
            )
            json = response.json()
            print(json)
            if json['rate']:  # Only save non-zero rates, in case we get nexus. Not the most efficient.
                tax, _ = super().get_or_create(location=location)
                tax.rate = json['rate'] / 100  # Make it decimal
                tax.save()
                return tax.rate
            else:
                return 0


class TaxRateCache(models.Model):
    rate = models.DecimalField(decimal_places=6, max_digits=10, null=True)
    location = models.CharField(max_length=100, primary_key=True)

    updated = models.DateTimeField(auto_now=True)
    taxes = TaxRateManager()

    def __str__(self):
        if self.rate:
            return "{}% rate for {}".format(self.rate * 100, self.location)
        else:
            return "{} (no tax set)".format(self.location)


def handle_null_money(val: Money or Decimal or None) -> Money:
    if isinstance(val, Money):
        return val
    if val is None:
        return Money(0, 'USD')
    return Money(val, 'USD')


def other_items_for_customer(user, cart=None, paid_only=False):
    lines = CheckoutLine.objects.filter(cart__owner=user,
                                        fulfilled=False,
                                        cancelled=False,
                                        cart__date_submitted__isnull=False,
                                        ).order_by('-cart__date_submitted')
    if paid_only:
        lines = lines.filter(cart__status=Cart.PAID)
    else:
        lines = lines.filter(cart__status__in=[Cart.SUBMITTED, Cart.PAID])

    if not cart:
        return lines
    return lines.exclude(cart__id=cart.id)
