import os
import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from checkout.models import Cart, ShippingAddress, CheckoutLine
from partner.models import Partner
from realaddress.models import RealCountry
from shop.models import Product, InventoryItem


class CheckoutTestCase(TestCase):
    def setUp(self):
        site, _ = Site.objects.get_or_create(name="Test site")
        product, _ = Product.objects.get_or_create(name="Test Product")
        partner, _ = Partner.objects.get_or_create(name="Test Partner")
        item, _ = InventoryItem.objects.get_or_create(product=product, partner=partner, price=Money(5, "USD"),
                                                      default_price=Money(5, "USD"))
        product2, _ = Product.objects.get_or_create(name="Test Product 2")
        item2, _ = InventoryItem.objects.get_or_create(product=product2, partner=partner, price=Money(5, "USD"),
                                                       default_price=Money(5, "USD"))

        us_country, _ = RealCountry.objects.get_or_create(iso_3166_1_a2="US")

        cart, _ = Cart.objects.get_or_create(site=site, email="Test@comicsgamesandthings.com", status=Cart.OPEN)
        address, _ = ShippingAddress.objects.get_or_create(
            first_name='Albi',
            last_name='Haskell',
            line1='line1',
            line2='line2',
            line4='verona',
            state='WI',
            postcode='53593',
            country=us_country,
        )

        cart.shipping_address = address
        cart.delivery_method = cart.SHIP_ALL
        cart.add(item)
        cart.add(item2)

        line = cart.lines.first()
        line.price_per_unit_override = Money(1, 'USD')
        line.save()

        cart.save()

    def test_pay(self):
        with mock.patch('checkout.models.now') as mock_now:
            mock_now.return_value = datetime.datetime(2026, 5, 31, tzinfo=datetime.timezone.utc)
            cart = Cart.objects.get(email="Test@comicsgamesandthings.com")
            has_quaderno = os.getenv("QUADERNO_URL")
            if has_quaderno:
                print("Testing tax with quaderno configured")
                # Assuming that the quaderno account is registered in wisconsin and the tax rate is still 5.5%
                cart.pay_amount(Money(10.55, "USD"))
                self.assertEqual(cart.status, Cart.PAID)
                self.assertEqual(cart.final_total, Money("10.55", 'USD'))
                self.assertEqual(cart.final_ship, Money("4.00", 'USD'))
                self.assertEqual(cart.final_tax, Money(".55", 'USD'))
            else:
                print("Will not test tax")
                cart.pay_amount(Money(10.00, "USD"))
                self.assertEqual(cart.status, Cart.PAID)
                self.assertEqual(cart.final_total, Money("10.00", 'USD'))
                self.assertEqual(cart.final_ship, Money("4.00", 'USD'))
                self.assertEqual(cart.final_tax, Money(".00", 'USD'))

    def test_pay_after_may_2026(self):
        with mock.patch('checkout.models.now') as mock_now:
            mock_now.return_value = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
            cart = Cart.objects.get(email="Test@comicsgamesandthings.com")
            has_quaderno = os.getenv("QUADERNO_URL")
            if has_quaderno:
                # 1 (item 1 override) + 5 (item 2) + 5.50 (ship) = 11.50
                # tax = 11.50 * 0.055 = 0.6325 -> 0.63
                # total = 11.50 + 0.63 = 12.13
                cart.pay_amount(Money(12.13, "USD"))
                self.assertEqual(cart.status, Cart.PAID)
                self.assertEqual(cart.final_ship, Money("5.50", 'USD'))
                self.assertEqual(cart.final_tax, Money(".63", 'USD'))
                self.assertEqual(cart.final_total, Money("12.13", 'USD'))
            else:
                # 1 + 5 + 5.50 = 11.50
                cart.pay_amount(Money(11.50, "USD"))
                self.assertEqual(cart.status, Cart.PAID)
                self.assertEqual(cart.final_ship, Money("5.50", 'USD'))
                self.assertEqual(cart.final_total, Money("11.50", 'USD'))

    def test_product_open_lines_view(self):
        product = Product.objects.get(name="Test Product")
        partner = Partner.objects.get(name="Test Partner")
        user = User.objects.create_user(username='testuser', password='password')
        partner.administrators.add(user)
        self.client.login(username='testuser', password='password')

        url = reverse('product_open_lines', kwargs={'partner_slug': partner.slug, 'product_id': product.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertContains(response, "Open")

    def test_clear_product_open_lines_view(self):
        product = Product.objects.get(name="Test Product")
        partner = Partner.objects.get(name="Test Partner")
        user = User.objects.create_user(username='testuser_clear', password='password')
        partner.administrators.add(user)
        self.client.login(username='testuser_clear', password='password')

        # Check initial lines
        self.assertTrue(CheckoutLine.objects.filter(item__product=product, cart__status=Cart.OPEN).exists())

        url = reverse('clear_product_open_lines', kwargs={'partner_slug': partner.slug, 'product_id': product.id})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('product_open_lines', kwargs={'partner_slug': partner.slug, 'product_id': product.id}))

        # Check lines are gone
        self.assertFalse(CheckoutLine.objects.filter(item__product=product, cart__status=Cart.OPEN).exists())

    def test_merge_line_copies_line_when_not_existing(self):
        site = Site.objects.get(name="Test site")
        product = Product.objects.get(name="Test Product")
        partner = Partner.objects.get(name="Test Partner")
        item = InventoryItem.objects.get(product=product, partner=partner)

        cart1 = Cart.objects.create(site=site, email="cart1@example.com", status=Cart.OPEN)
        cart1.add(item, quantity=2)
        cart1_line = cart1.lines.first()

        cart2 = Cart.objects.create(site=site, email="cart2@example.com", status=Cart.OPEN)
        self.assertEqual(cart2.lines.count(), 0)

        cart2.merge_line(cart1_line)

        # cart2 should now have the line
        self.assertEqual(cart2.lines.count(), 1)
        cart2_line = cart2.lines.first()
        self.assertEqual(cart2_line.item, item)
        self.assertEqual(cart2_line.quantity, 2)
        self.assertNotEqual(cart2_line.id, cart1_line.id)

        # cart1 should still have the original line intact (not moved or deleted)
        self.assertEqual(cart1.lines.count(), 1)
        cart1_line.refresh_from_db()
        self.assertEqual(cart1_line.cart, cart1)
        self.assertEqual(cart1_line.quantity, 2)

    def test_merge_line_copies_and_updates_quantity_when_existing(self):
        site = Site.objects.get(name="Test site")
        product = Product.objects.get(name="Test Product")
        partner = Partner.objects.get(name="Test Partner")
        item = InventoryItem.objects.get(product=product, partner=partner)

        cart1 = Cart.objects.create(site=site, email="cart1@example.com", status=Cart.OPEN)
        cart1.add(item, quantity=2)
        cart1_line = cart1.lines.first()

        cart2 = Cart.objects.create(site=site, email="cart2@example.com", status=Cart.OPEN)
        cart2.add(item, quantity=3)

        cart2.merge_line(cart1_line, add_quantities=True)

        # cart2 quantity should be 5
        self.assertEqual(cart2.lines.count(), 1)
        self.assertEqual(cart2.lines.first().quantity, 5)

        # cart1 should still have the original line intact (not deleted)
        self.assertEqual(cart1.lines.count(), 1)
        cart1_line.refresh_from_db()
        self.assertEqual(cart1_line.cart, cart1)
        self.assertEqual(cart1_line.quantity, 2)
