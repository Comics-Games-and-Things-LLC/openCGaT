import datetime
from decimal import Decimal

from django.conf.global_settings import AUTH_USER_MODEL
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Subquery
from django.template.defaultfilters import slugify
from djmoney.models.fields import MoneyField
from pytz import utc

from checkout.models import Cart, CheckoutLine
from shop.models import Publisher

# Create your models here.
PERCENTAGE_VALIDATOR = [MinValueValidator(0), MaxValueValidator(100)]


class Referrer(models.Model):
    name = models.CharField(max_length=200)
    referrer_is_partner = models.ForeignKey("partner.Partner", on_delete=models.PROTECT, blank=True, null=True)
    slug = models.SlugField(max_length=200)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        return super(Referrer, self).save(*args, **kwargs)


class DiscountCode(models.Model):
    code = models.SlugField(max_length=80)

    # If made by a particular partner, that partner can edit this.
    # Otherwise, it's site wide and not editable except through admin.
    partner = models.ForeignKey("partner.Partner", on_delete=models.SET_NULL, blank=True, null=True)

    referrer = models.ForeignKey(Referrer, on_delete=models.PROTECT, null=True, blank=True)
    expires_on = models.DateTimeField(blank=True, null=True)
    once_per_customer = models.BooleanField(default=False)
    restrict_to_publishers = models.BooleanField(default=False)
    exclude_publishers = models.BooleanField(default=False)
    publishers = models.ManyToManyField("shop.Publisher", blank=True)
    min_cart_for_discount = MoneyField(decimal_places=2, max_digits=19, null=True)
    in_store_only = models.BooleanField(default=False)

    def validate_code_for_cart(self, cart):
        """
        Determines if this code is valid at all, and sets an error message for the user.
        :param cart:
        :return:
        """
        if self.in_store_only and not cart.at_pos:
            cart.discount_code_message = f"The code '{self}' is only available in-store. Please come in person."
            cart.discount_code = None
            cart.save()
            return False
        if self.expires_on and datetime.datetime.now().replace(tzinfo=utc) > self.expires_on:
            cart.discount_code_message = "The code '{}' has expired".format(self)
            cart.discount_code = None
            cart.save()
            return False
        if self.once_per_customer:
            carts_with_code = Cart.submitted.filter(discount_code=self)
            if (cart.owner is None and cart.email is not None and carts_with_code.filter(email=cart.email,
                                                                                         discount_code=self).exists()) or \
                    (cart.owner is not None and carts_with_code.filter(owner=cart.owner, discount_code=self).exists()):
                cart.discount_code_message = "The code '{}' is only valid once per customer".format(self)
                cart.discount_code = None
                cart.save()
                return False  # If this person has used the code before, they can't ues it again
        cart.discount_code_message = None
        cart.discount_code = self
        cart.save()
        return True

    def apply_discount_to_line_item(self, line):
        """
        Returns a tuple of if there is a discount for this item, and the new price for this item.
        :param line: cart line with item.
        :return: (applicable, new_price)
        """
        prev_message = line.discount_code_message
        found_partner = False
        for discount in self.partner_discounts.filter(partner=line.item.partner):  # Try each discount from the partner
            if discount.discount_percentage == 0:
                return False, line.item.price # Vague performance improvement, skip all these other checks if there's no discount.
            found_partner = True
            if self.min_cart_for_discount and (line.cart.get_pre_discount_subtotal() < self.min_cart_for_discount):
                line.discount_code_message = "The code '{}' requires {} to activate".format(self,
                                                                                            self.min_cart_for_discount)
                break  # exit the loop early to mark this line as not eligible.
            if line.item.product.publisher is None:
                if self.restrict_to_publishers:
                    line.discount_code_message = f"The code '{self}' is not applicable to items with no publisher"
                    break  # exit the loop early to mark this line as not eligible.
            else:
                if line.item.product.publisher.no_discount_codes:
                    line.discount_code_message = (f"Items from {line.item.product.publisher} are not eligible for any "
                                                  f"discounts")
                    break  # exit the loop early to mark this line as not eligible.

                if (self.exclude_publishers and self.publishers.filter(id=line.item.product.publisher.id)) or (
                        self.restrict_to_publishers and not self.publishers.filter(id=line.item.product.publisher.id)):
                    line.discount_code_message = "The code '{}' is not applicable to items from {}".format(self,
                                                                                                           line.item.product.publisher)
                    break  # exit the loop early to mark this line as not eligible.
            # Eligible for the discount:
            line.discount_code_message = None
            if line.discount_code_message != prev_message:
                print("Clearing discount code message")
                line.save()
            old_price = line.item.price
            if line.price_per_unit_override:
                old_price = line.price_per_unit_override
            new_price = old_price * ((100 - discount.discount_percentage) / Decimal(100))
            return True, new_price
        if not found_partner:
            line.discount_code_message = "The code '{}' does not apply for items from the seller '{}'".format(self,
                                                                                                              line.item.partner)
        if line.discount_code_message != prev_message:
            print(f"Setting discount code message to '{line.discount_code_message}' from '{prev_message}")
            line.save()

        return False, line.item.price

    def get_applicable_lines(self, existing_query=None):

        publishers_excluded_from_discounts = Publisher.objects.filter(no_discount_codes=True)

        if existing_query is None:
            existing_query = CheckoutLine.objects.all()
        applicable_lines = (
            existing_query
            .exclude(cart__status=Cart.CANCELLED, cancelled=True)
            .filter(cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED], cart__discount_code=self)
            .exclude(item__product__publisher__in=Subquery(publishers_excluded_from_discounts.values('id')))
            .order_by("cart__date_paid")
        )
        if self.restrict_to_publishers:
            applicable_lines =applicable_lines.filter(item__product__publisher__in=self.publishers.all())
        if self.exclude_publishers:
            applicable_lines = applicable_lines.exclude(item__product__publisher__in=self.publishers.all())

        return applicable_lines

    def save(self, *args, **kwargs):
        self.code = self.code.lower()
        return super(DiscountCode, self).save(*args, **kwargs)

    def __str__(self):
        return self.code


class PartnerDiscount(models.Model):
    code = models.ForeignKey(DiscountCode, on_delete=models.CASCADE, related_name='partner_discounts')
    partner = models.ForeignKey("partner.Partner", on_delete=models.PROTECT)
    discount_percentage = models.IntegerField(validators=PERCENTAGE_VALIDATOR)
    referrer_kickback = models.IntegerField(validators=PERCENTAGE_VALIDATOR)

    def __str__(self):
        return "{}% off from {} using code {}".format(self.discount_percentage, self.partner, self.code)


class CodeUsage(models.Model):
    """
    Keeps track of every cart that has come in through a referral usage, or any discount code that was tried.
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    code = models.ForeignKey(DiscountCode, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, blank=True, null=True)
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return f"{self.code} was used at {self.timestamp} for cart {self.cart}"
