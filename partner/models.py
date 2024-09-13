import datetime

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from wagtail.fields import RichTextField

import realaddress.abstract_models


class Partner(models.Model):
    name = models.CharField(max_length=200)

    description = RichTextField()

    administrators = models.ManyToManyField(User, blank=True, related_name="admin_of")
    retail_partner = models.BooleanField(default=False)
    digital_partner = models.BooleanField(default=False)
    crowdfunding_features = models.BooleanField(default=False)
    phys_cut = models.FloatField(default=.98)
    digital_cut = models.FloatField(default=.96)
    enable_mto = models.BooleanField(default=False)

    slug = models.SlugField(unique=True, blank=True, max_length=200)

    hide = models.BooleanField(default=False)

    acct_balance = MoneyField(max_digits=14, decimal_places=4, default_currency='USD', default=0)

    in_store_tax_rate = models.FloatField(default=.055, help_text="Percent in decimal form( ex .055)")

    site = models.OneToOneField(Site, on_delete=models.SET_NULL, blank=True, null=True, related_name='partner')

    static_prefix = models.CharField(max_length=20, default='default')

    default_download_all = models.BooleanField(default=True)

    address_and_hours_info = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Partner, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    def reset_balance(self):
        self.acct_balance = Money(0, "USD")
        for pt in self.partnertransaction_set.all():
            pt.reset()
        self.save()

    def update_balance(self):
        billing_history = self.partnertransaction_set.filter(applied_to_account=False).order_by('timestamp')
        for pt in billing_history:
            pt.apply()

    def get_cut(self, item):
        """
        Returns the physical or digital cut (out of 1) based on the type of the item
        :param item:
        :return:
        """

        if isinstance(item, apps.get_model('digitalitems', 'DigitalItem')) \
                or isinstance(item, apps.get_model('subscriptions', 'SubscriptionItem')):
            return self.digital_cut
        # if isinstance(item, apps.get_model('shop', 'InventoryItem')) \
        #         or isinstance(item, apps.get_model('shop', 'MadeToOrder')):
        return self.phys_cut


class PartnerAddress(realaddress.abstract_models.AbstractPartnerAddress):
    pass


class PartnerTransaction(models.Model):
    PLATFORM_CHARGE, PURCHASE, MANUAL_ADJUSTMENT, PAYMENT, SUBSCRIPTION = (
        "Platform Charge", "Purchase", "Manual", "Payment", "Subscription")
    PLATFORM_TRANSACTION_TYPES = (
        (PLATFORM_CHARGE, "A fee from the platform"),
        (PURCHASE, "The purchase of an item on platform and the fees associated"),
        (MANUAL_ADJUSTMENT, "Manual adjustment (see comments)"),
        (PAYMENT, "A payment of the account balance"),
        (SUBSCRIPTION, "A subscription charged to a user"),
    )
    type = models.CharField(
        "type", max_length=128, default=None, choices=PLATFORM_TRANSACTION_TYPES, null=True)
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)  # This field is overwritten by pledges, etc
    created_timestamp = models.DateTimeField(auto_now_add=True)  # This field is not
    transaction_total = MoneyField(max_digits=14, decimal_places=4, default_currency='USD', blank=True, null=True)
    transaction_subtotal = MoneyField(max_digits=14, decimal_places=4, default_currency='USD')
    transaction_fees = MoneyField(max_digits=14, decimal_places=4, default_currency='USD')
    applied_to_account = models.BooleanField(default=False)
    balance_after_apply = MoneyField(max_digits=14, decimal_places=4, default_currency='USD', blank=True, null=True)

    comments = models.TextField(blank=True, null=True)

    is_summary = models.BooleanField(default=False)
    summarized_in = models.ForeignKey('PartnerTransaction', blank=True, null=True, default=None,
                                      related_name="Summarizing", on_delete=models.SET_NULL)

    cancelled = models.BooleanField(default=False)

    @property
    def partner_cut(self):
        return self.transaction_subtotal - self.transaction_fees

    @property
    def platform_cut(self):
        if self.collected_less_tax is not None:
            return self.collected_less_tax - self.partner_cut

    @property
    def cart(self):
        try:
            Cart = apps.get_model('checkout', 'Cart')
            return Cart.submitted.filter(partner_transactions=self).first()
        except Exception as e:
            print(e)
            return None

    @property
    def tax(self):
        cart = self.cart
        if cart is not None:
            return cart.final_tax

    @property
    def collected_less_tax(self):
        tax = self.tax
        if tax is not None and self.transaction_total is not None:
            return self.transaction_total - self.tax

    def reset(self):
        if self.is_summary:
            self.delete()
        else:
            self.applied_to_account = False
            self.balance_after_apply = None
            try:  # This is in a try block to prevent caching issues
                self.summarized_in.delete()
            except PartnerTransaction.DoesNotExist:
                pass
            except AttributeError:
                pass
            self.summarized_in = None
            self.save()

    def apply(self):
        with transaction.atomic():
            pt = PartnerTransaction.objects.select_for_update().get(id=self.id)  # Use lock on object
            if not pt.applied_to_account and not pt.cancelled and not pt.is_summary:
                partner = Partner.objects.select_for_update().get(id=self.partner.id)
                balance = partner.acct_balance
                balance = balance + pt.partner_cut
                pt.summarize()
                pt.balance_after_apply = balance
                partner.acct_balance = balance
                partner.save()
                pt.applied_to_account = True
                pt.save()

    def cancel(self):
        with transaction.atomic():
            if self.applied_to_account and not self.cancelled and not self.is_summary:
                balance = Partner.objects.select_for_update().get(id=self.partner.id).acct_balance
                balance = balance - self.partner_cut
                self.summarize()
                self.balance_after_apply = balance
                self.partner.acct_balance = balance
                self.partner.save()
            self.cancelled = True
            self.save()

    def summarize(self):
        """
        This function groups a platform charge or subscription with other payments of the same type
        :return:
        """
        if self.type == self.PLATFORM_CHARGE or self.type == self.SUBSCRIPTION:
            summary_month = datetime.datetime(self.timestamp.year, self.timestamp.month, 1)
            summary, created = PartnerTransaction.objects.get_or_create(is_summary=True,
                                                                        timestamp=summary_month,
                                                                        type=self.type,
                                                                        partner=self.partner,
                                                                        defaults={
                                                                            'transaction_fees': Money(0, 'USD'),
                                                                            'transaction_subtotal': Money(0, 'USD'),
                                                                        })
            if created:
                summary.timestamp = summary_month
            summary.balance_after_apply = self.balance_after_apply
            if self.transaction_total and summary.transaction_total:
                summary.transaction_total += self.transaction_total
            if self.transaction_subtotal:
                summary.transaction_subtotal += self.transaction_subtotal
            if self.transaction_fees:
                summary.transaction_fees += self.transaction_fees
            summary.save()
            self.summarized_in = summary
            self.save()

    def __str__(self):
        if self.is_summary:
            return "{0} {1} {2} Summary from {3}".format(self.partner.name, self.type, self.partner_cut,
                                                         self.timestamp)
        return "{0} {1} {2} {3}".format(self.partner.name, self.type, self.partner_cut, self.timestamp)

    def migrate_to_billing_event(self):
        """
        Take a partner transaction and create a  billing event from it.
        :return:  Migrated object, or none if a billing summary
        """
        if self.is_summary:
            return None
        from billing.models import BillingEvent
        be = BillingEvent.objects.get_or_create(migrated_from=self,
                                                timestamp=self.created_timestamp)
        if self.type == self.PURCHASE:
            be.type = BillingEvent.COLLECTED_FROM_CUSTOMER
            # TODO: Add Cart information
        elif self.type == self.PAYMENT:
            if self.transaction_subtotal > 0:
                be.type = BillingEvent.PAYMENT
            if self.transaction_subtotal < 0:
                be.type = BillingEvent.PAYOUT
        be.save()
        return be


def get_partner(request, manage_partner_slug=None, objects=None):
    """
    :param request: django request to pull site and user from
    :param manage_partner_slug: the slug to find a partner of if we are in manage mode
    :param objects: a set of objects to check to see if we can manage
    :return: A tuple of the partner and if this is a management mode
    """
    if manage_partner_slug:
        return get_partner_or_401(request, manage_partner_slug, objects), True
    try:
        if request.site.partner:
            return request.site.partner, False
    except Exception:
        pass
    return None, False


def get_partner_or_401(request, partner_slug, objects=None):
    site_partner_slug = None
    try:
        if request.site.partner:
            site_partner_slug = request.site.partner
    except Exception:
        pass
    if site_partner_slug:
        if partner_slug != request.site.partner.slug:
            raise PermissionDenied
    if objects is None:
        objects = []
    partner = get_object_or_404(Partner, slug=partner_slug)
    if request.user not in partner.administrators.all():
        raise PermissionDenied
    for item in objects:
        if item and item.partner != partner:
            raise PermissionDenied
    return partner
