from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase, Client
from django.urls import reverse
from djmoney.money import Money

from partner.models import Partner
from shop.models import Product, InventoryItem
from print_queue.models import PrintQueueItem


class PrintQueueTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain="test.com", name="test")
        self.partner = Partner.objects.create(name="Test Partner", slug="test-partner")
        self.user = User.objects.create_user(username="testuser", password="password")
        self.partner.administrators.add(self.user)

        self.other_partner = Partner.objects.create(name="Other Partner", slug="other-partner")
        self.other_user = User.objects.create_user(username="otheruser", password="password")
        self.other_partner.administrators.add(self.other_user)

        self.product1 = Product.objects.create(name="Product 1", barcode="111111")
        self.item1 = InventoryItem.objects.create(
            product=self.product1,
            partner=self.partner,
            price=Money(10, "USD"),
            default_price=Money(10, "USD"),
            current_inventory=5
        )
        self.queue_item1 = PrintQueueItem.objects.create(
            inventory_item=self.item1,
            quantity_at_adjustment=5,
            old_price=Money(8, "USD"),
            new_price=Money(10, "USD")
        )

        self.product2 = Product.objects.create(name="Product 2", barcode="222222")
        self.item2 = InventoryItem.objects.create(
            product=self.product2,
            partner=self.partner,
            price=Money(20, "USD"),
            default_price=Money(20, "USD"),
            current_inventory=10
        )
        self.queue_item2 = PrintQueueItem.objects.create(
            inventory_item=self.item2,
            quantity_at_adjustment=10,
            old_price=Money(15, "USD"),
            new_price=Money(20, "USD")
        )

        # Item for other partner
        self.product_other = Product.objects.create(name="Other Product", barcode="333333")
        self.item_other = InventoryItem.objects.create(
            product=self.product_other,
            partner=self.other_partner,
            price=Money(30, "USD"),
            default_price=Money(30, "USD"),
            current_inventory=3
        )
        self.queue_item_other = PrintQueueItem.objects.create(
            inventory_item=self.item_other,
            quantity_at_adjustment=3,
            old_price=Money(25, "USD"),
            new_price=Money(30, "USD")
        )

        self.client = Client()

    def test_print_queue_list_view(self):
        self.client.login(username="testuser", password="password")
        url = reverse('print_queue_list', kwargs={'partner_slug': self.partner.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Product 1")
        self.assertContains(response, "Product 2")
        self.assertNotContains(response, "Other Product")
        self.assertContains(response, "Mark all finished")
        self.assertContains(response, "markAllFinished()")

    def test_mark_restickered(self):
        self.client.login(username="testuser", password="password")
        url = reverse('mark_restickered', kwargs={'partner_slug': self.partner.slug, 'item_id': self.queue_item1.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success'})

        self.queue_item1.refresh_from_db()
        self.assertTrue(self.queue_item1.restickered)
        self.assertIsNotNone(self.queue_item1.restickered_at)

        self.queue_item2.refresh_from_db()
        self.assertFalse(self.queue_item2.restickered)

    def test_mark_all_restickered(self):
        self.client.login(username="testuser", password="password")
        url = reverse('mark_all_restickered', kwargs={'partner_slug': self.partner.slug})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success'})

        self.queue_item1.refresh_from_db()
        self.queue_item2.refresh_from_db()
        self.queue_item_other.refresh_from_db()

        self.assertTrue(self.queue_item1.restickered)
        self.assertIsNotNone(self.queue_item1.restickered_at)
        self.assertTrue(self.queue_item2.restickered)
        self.assertIsNotNone(self.queue_item2.restickered_at)

        # Other partner's items must not be affected
        self.assertFalse(self.queue_item_other.restickered)
        self.assertIsNone(self.queue_item_other.restickered_at)

    def test_mark_all_finished_url_alias(self):
        self.client.login(username="testuser", password="password")
        url = reverse('mark_all_finished', kwargs={'partner_slug': self.partner.slug})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'success'})

        self.queue_item1.refresh_from_db()
        self.assertTrue(self.queue_item1.restickered)

    def test_mark_all_restickered_unauthorized(self):
        # User not logged in
        url = reverse('mark_all_restickered', kwargs={'partner_slug': self.partner.slug})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

        # User logged in as another partner admin
        self.client.login(username="otheruser", password="password")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_mark_all_restickered_requires_post(self):
        self.client.login(username="testuser", password="password")
        url = reverse('mark_all_restickered', kwargs={'partner_slug': self.partner.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
