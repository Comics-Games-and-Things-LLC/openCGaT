import datetime

import pytz
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from djmoney.money import Money

from checkout.models import Cart, CheckoutLine
from partner.models import Partner
from shop.models import Product, InventoryItem


class POSSalesDayTest(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain="test.com", name="test")
        self.partner = Partner.objects.create(name="Test Partner", slug="test-partner")
        self.user = User.objects.create_user(username="testuser", password="password")
        self.partner.administrators.add(self.user)

        self.product = Product.objects.create(name="Test Product")
        self.item = InventoryItem.objects.create(
            product=self.product,
            partner=self.partner,
            price=Money(10, "USD"),
            default_price=Money(10, "USD"),
            current_inventory=50
        )

        self.client = Client()
        self.client.login(username="testuser", password="password")

        # Create a POS sale today
        tz = pytz.timezone('US/Central')
        today_central = timezone.now().astimezone(tz).date()
        dt_central = tz.localize(datetime.datetime.combine(today_central, datetime.time(12, 0)))

        self.cart = Cart.objects.create(
            site=self.site,
            status=Cart.PAID,
            at_pos=True,
            date_submitted=dt_central,
            pickup_partner=self.partner
        )
        CheckoutLine.objects.create(
            cart=self.cart,
            item=self.item,
            quantity=2,
        )

    def test_in_store_sales_for_day_view(self):
        # The URL is included under partner/<partner_slug>/orders/
        url = reverse('in_store_sales_for_day', kwargs={'partner_slug': self.partner.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertContains(response, wrap_in_td("2"))  # Quantity sold
        self.assertContains(response, wrap_in_td("50"))  # Inventory

    def test_in_store_sales_for_day_filter(self):
        # Create a sale for yesterday
        tz = pytz.timezone('US/Central')
        yesterday = (timezone.now().astimezone(tz) - datetime.timedelta(days=1)).date()
        dt_yesterday = tz.localize(datetime.datetime.combine(yesterday, datetime.time(12, 0)))

        cart_yesterday = Cart.objects.create(
            site=self.site,
            status=Cart.PAID,
            at_pos=True,
            date_submitted=dt_yesterday,
            pickup_partner=self.partner
        )
        CheckoutLine.objects.create(
            cart=cart_yesterday,
            item=self.item,
            quantity=5,
        )

        url = reverse('in_store_sales_for_day', kwargs={'partner_slug': self.partner.slug})

        # Check today (should only have 2)
        response = self.client.get(url)
        self.assertContains(response, wrap_in_td("2"))
        self.assertNotContains(response, wrap_in_td("5"))

        # Check yesterday
        response = self.client.get(url, {'date': yesterday.strftime('%Y-%m-%d')})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, wrap_in_td("5"))
        self.assertNotContains(response, wrap_in_td("2"))


def wrap_in_td(text):
    return f"""<td>
                        {text}
                    </td>"""
