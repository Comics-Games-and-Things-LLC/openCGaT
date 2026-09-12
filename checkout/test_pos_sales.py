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
from shop.models import Product, InventoryItem, Category


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
        self.assertContains(response, "Print Daily Sales")
        self.assertContains(response, "print_daily_sales()")

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

    def test_in_store_sales_sorted_by_top_level_categories(self):
        # Setup category hierarchy:
        # Miniatures (top-level) -> Warhammer (sub)
        # Board Games (top-level) -> Strategy (sub)
        cat_miniatures = Category.objects.create(name="Miniatures")
        cat_warhammer = Category.objects.create(name="Warhammer", parent=cat_miniatures)
        cat_boardgames = Category.objects.create(name="Board Games")
        cat_strategy = Category.objects.create(name="Strategy", parent=cat_boardgames)

        prod_mini_sub = Product.objects.create(name="Space Marine Box")
        prod_mini_sub.categories.add(cat_warhammer)
        item_mini_sub = InventoryItem.objects.create(
            product=prod_mini_sub, partner=self.partner,
            price=Money(30, "USD"), default_price=Money(30, "USD"), current_inventory=10
        )

        prod_board_sub = Product.objects.create(name="Catan Expansion")
        prod_board_sub.categories.add(cat_strategy)
        item_board_sub = InventoryItem.objects.create(
            product=prod_board_sub, partner=self.partner,
            price=Money(40, "USD"), default_price=Money(40, "USD"), current_inventory=5
        )

        prod_board_root = Product.objects.create(name="Base Catan")
        prod_board_root.categories.add(cat_boardgames)
        item_board_root = InventoryItem.objects.create(
            product=prod_board_root, partner=self.partner,
            price=Money(50, "USD"), default_price=Money(50, "USD"), current_inventory=8
        )

        # Add lines to today's cart
        CheckoutLine.objects.create(cart=self.cart, item=item_mini_sub, quantity=1)
        CheckoutLine.objects.create(cart=self.cart, item=item_board_sub, quantity=1)
        CheckoutLine.objects.create(cart=self.cart, item=item_board_root, quantity=1)

        url = reverse('in_store_sales_for_day', kwargs={'partner_slug': self.partner.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        sales = response.context['sales']
        product_names = [s['item'].product.name for s in sales]

        # Product without category ("Test Product") has top-level category ""
        # "Board Games" products should come before "Miniatures" products
        # Verify relative ordering
        idx_uncategorized = product_names.index("Test Product")
        idx_catan_exp = product_names.index("Catan Expansion")
        idx_catan_base = product_names.index("Base Catan")
        idx_space_marine = product_names.index("Space Marine Box")

        self.assertLess(idx_uncategorized, idx_catan_exp)
        self.assertLess(idx_catan_exp, idx_space_marine)
        self.assertLess(idx_catan_base, idx_space_marine)


def wrap_in_td(text):
    return f"""<td>{text}</td>"""
