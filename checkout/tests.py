import os
import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
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

    def test_merged_cart_changing_status_sends_email_and_proceeds(self):
        site = Site.objects.get(name="Test site")
        cart = Cart.objects.create(site=site, email="merged@example.com", status=Cart.MERGED)
        mail.outbox.clear()

        # Change status away from MERGED
        cart.status = Cart.OPEN
        cart.save()

        # Verify status change proceeded
        cart.refresh_from_db()
        self.assertEqual(cart.status, Cart.OPEN)

        # Verify email was sent to admin referencing issue #272
        self.assertGreater(len(mail.outbox), 0)
        sent_email = mail.outbox[-1]
        self.assertIn("#272", sent_email.body)
        self.assertIn(str(cart.id), sent_email.body)
        self.assertIn("Merged", sent_email.body)
        self.assertIn("Open", sent_email.body)

    def test_merged_cart_saving_same_status_does_not_send_email(self):
        site = Site.objects.get(name="Test site")
        cart = Cart.objects.create(site=site, email="merged_same@example.com", status=Cart.MERGED)
        mail.outbox.clear()

        # Save again with same status
        cart.email = "merged_same2@example.com"
        cart.save()

        self.assertEqual(len(mail.outbox), 0)

    def test_open_cart_changing_to_merged_does_not_send_warning_email(self):
        site = Site.objects.get(name="Test site")
        cart = Cart.objects.create(site=site, email="open_to_merged@example.com", status=Cart.OPEN)
        mail.outbox.clear()

        # Change from OPEN to MERGED
        cart.status = Cart.MERGED
        cart.save()

        self.assertEqual(len(mail.outbox), 0)
        cart.refresh_from_db()
        self.assertEqual(cart.status, Cart.MERGED)

    def test_checkout_complete_confirmation_page_content(self):
        site = Site.objects.get(name="Test site")
        cart = Cart.objects.create(site=site, email="order_confirmed@example.com", status=Cart.SUBMITTED)
        url = reverse('checkout_complete', kwargs={'order_id': cart.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Checkout complete")
        self.assertContains(response, "confirmation email")
        self.assertContains(response, "spam")
        self.assertContains(response, "reach out")

    def test_other_items_for_customer_by_owner_and_email(self):
        from checkout.models import other_items_for_customer
        from allauth.account.models import EmailAddress

        site = Site.objects.get(name="Test site")
        partner = Partner.objects.get(name="Test Partner")
        product = Product.objects.get(name="Test Product")
        product2 = Product.objects.get(name="Test Product 2")
        item1 = InventoryItem.objects.get(product=product, partner=partner)
        item2 = InventoryItem.objects.get(product=product2, partner=partner)

        user1 = User.objects.create_user(username='customer1', email='customer1@example.com', password='password')
        EmailAddress.objects.create(user=user1, email='customer1_alt@example.com', verified=True, primary=False)

        # Cart 1: Paid order owned by user1
        cart1 = Cart.objects.create(site=site, owner=user1, email='customer1@example.com', status=Cart.PAID,
                                    date_submitted=timezone.now())
        cart1.add(item1, quantity=1)

        # Cart 1b: Second paid order owned by user1
        cart1b = Cart.objects.create(site=site, owner=user1, email='customer1@example.com', status=Cart.PAID,
                                     date_submitted=timezone.now())
        cart1b.add(item2, quantity=1)

        # Cart 2: Guest paid order with same email as user1's primary email
        cart2 = Cart.objects.create(site=site, owner=None, email='customer1@example.com', status=Cart.PAID,
                                    date_submitted=timezone.now())
        cart2.add(item2, quantity=2)

        # Cart 3: Guest paid order with user1's alternate email
        cart3 = Cart.objects.create(site=site, owner=None, email='customer1_alt@example.com', status=Cart.PAID,
                                    date_submitted=timezone.now())
        cart3.add(item1, quantity=3)

        # Cart 4: Order for unrelated email
        user2 = User.objects.create_user(username='customer2', email='customer2@example.com', password='password')
        cart4 = Cart.objects.create(site=site, owner=user2, email='customer2@example.com', status=Cart.PAID,
                                    date_submitted=timezone.now())
        cart4.add(item2, quantity=1)

        # When viewing other items for cart1 (owned by user1), since user is set, it only matches user's carts (cart1b)
        # and does NOT fallback to email to match guest orders cart2 or cart3.
        other_items_cart1 = cart1.get_other_items_for_customer(paid_only=True)
        self.assertIsNotNone(other_items_cart1)
        cart_ids = [line.cart.id for line in other_items_cart1]
        self.assertIn(cart1b.id, cart_ids)
        self.assertNotIn(cart1.id, cart_ids)
        self.assertNotIn(cart2.id, cart_ids)
        self.assertNotIn(cart3.id, cart_ids)
        self.assertNotIn(cart4.id, cart_ids)

        # Direct user query only returns user's carts
        user_items = other_items_for_customer(user1, paid_only=True)
        user_cart_ids = [line.cart.id for line in user_items]
        self.assertIn(cart1.id, user_cart_ids)
        self.assertIn(cart1b.id, user_cart_ids)
        self.assertNotIn(cart2.id, user_cart_ids)
        self.assertNotIn(cart3.id, user_cart_ids)
        self.assertNotIn(cart4.id, user_cart_ids)

        # When viewing other items for guest cart2 (email: customer1@example.com, owner=None), user is not set,
        # so it falls back to email matching and includes cart1, cart1b (matched by user email)
        other_items_cart2 = cart2.get_other_items_for_customer(paid_only=True)
        self.assertIsNotNone(other_items_cart2)
        cart_ids_guest = [line.cart.id for line in other_items_cart2]
        self.assertIn(cart1.id, cart_ids_guest)
        self.assertIn(cart1b.id, cart_ids_guest)
        self.assertNotIn(cart2.id, cart_ids_guest)
        self.assertNotIn(cart4.id, cart_ids_guest)

    def test_partner_order_details_shows_other_items_for_guest_and_user_orders(self):
        site = Site.objects.get(name="Test site")
        partner = Partner.objects.get(name="Test Partner")
        product = Product.objects.get(name="Test Product")
        product2 = Product.objects.get(name="Test Product 2")
        item1 = InventoryItem.objects.get(product=product, partner=partner)
        item2 = InventoryItem.objects.get(product=product2, partner=partner)

        admin_user = User.objects.create_user(username='admin_partner', password='password')
        partner.administrators.add(admin_user)
        self.client.login(username='admin_partner', password='password')

        # Cart A: Guest order submitted with email
        cart_a = Cart.objects.create(site=site, owner=None, email='shared_email@example.com', status=Cart.PAID,
                                     date_submitted=timezone.now())
        cart_a.add(item1, quantity=1)

        # Cart B: Another order with same email
        cart_b = Cart.objects.create(site=site, owner=None, email='shared_email@example.com', status=Cart.PAID,
                                     date_submitted=timezone.now())
        cart_b.add(item2, quantity=4)

        # Details view for Cart A should show Cart B in other items
        url_a = reverse('partner_order_details', kwargs={'partner_slug': partner.slug, 'cart_id': cart_a.id})
        response = self.client.get(url_a)
        self.assertEqual(response.status_code, 200)
        self.assertIn('other_items_for_customer', response.context)
        other_items = response.context['other_items_for_customer']
        self.assertIsNotNone(other_items)
        self.assertEqual(other_items.count(), 1)
        self.assertEqual(other_items.first().cart.id, cart_b.id)
        self.assertContains(response, f"/{partner.slug}/orders/{cart_b.id}/")

        # Printout view for Cart A
        url_print = reverse('partner_order_printout', kwargs={'partner_slug': partner.slug, 'cart_id': cart_a.id})
        response_print = self.client.get(url_print)
        self.assertEqual(response_print.status_code, 200)
        self.assertIn('other_items_for_customer', response_print.context)
        self.assertEqual(response_print.context['other_items_for_customer'].count(), 1)
