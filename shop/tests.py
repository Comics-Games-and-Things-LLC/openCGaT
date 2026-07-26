import datetime

from django.contrib.sites.models import Site
from django.test import TestCase
from djmoney.money import Money

from checkout.models import Cart
from partner.models import Partner
from shop.models import Product, InventoryItem, Publisher
from intake.models import Distributor, DistributorInventoryFile, DistributorInventoryLine, DistItem
from shop.views_api import item_list_filter


class StatusTestCases(TestCase):

    @staticmethod
    def create_base_product():
        site, _ = Site.objects.get_or_create(name="Test site")
        partner, _ = Partner.objects.get_or_create(name="Test Partner")
        product = Product.objects.create(name=f"Test Product - {datetime.datetime.now()}",
                                         release_date=datetime.date.today(),
                                         visible_on_release=True,
                                         purchasable_on_release=True,
                                         preorder_or_secondary_release_date=datetime.date.today(),
                                         visible_on_preorder_secondary=True,
                                         purchasable_on_preorder_secondary=True,
                                         page_is_draft=False,
                                         )
        product.save()
        item = InventoryItem.objects.create(product=product, partner=partner,
                                            price=Money(5, "USD"),
                                            default_price=Money(5, "USD"),
                                            )
        cart = Cart.objects.create(site=site, email="Test@comicsgamesandthings.com", status=Cart.OPEN)
        cart.delivery_method = cart.PICKUP_ALL
        line, _ = cart.add(item)
        return product, item, line

    def test_status_preorder_allocated(self):
        # Arrange
        product, item, line = self.create_base_product()
        product.release_date = datetime.date.today() + datetime.timedelta(days=1)
        product.save()
        item.preallocated = True
        item.preallocated_inventory = 1
        item.save()

        # Assert
        button_status = item.button_status()
        self.assertEqual(button_status["text"], "Preorder")
        self.assertEqual(button_status["enabled"], True)

        self.assertEqual(line.status_text, "Preorder")

        # Act
        line.cart.submit()

        # Assert
        self.assertEqual(line.status_text, "Submitted", "Text after submit")

    def test_status_preorder_underallocated(self):
        # Arrange
        product, item, line = self.create_base_product()
        product.release_date = datetime.date.today() + datetime.timedelta(days=1)
        product.save()
        item.preallocated = True
        item.preallocated_inventory = 1
        item.save()

        line.quantity = 2
        line.save()

        # Assert
        button_status = item.button_status()
        self.assertEqual(button_status["text"], "Preorder")
        self.assertEqual(button_status["enabled"], True)

        self.assertEqual(line.status_text, "1 preallocated \n1 will be preordered")

        # Act
        line.cart.submit()

        # Assert
        self.assertEqual(line.status_text, "Submitted", "Text after submit")

    def test_status_preorder_no_allocation(self):
        # Arrange
        product, item, line = self.create_base_product()
        product.release_date = datetime.date.today() + datetime.timedelta(days=1)
        product.save()
        item.preallocated = True
        item.preallocated_inventory = 0
        item.save()

        line.quantity = 1
        line.save()

        # Assert
        button_status = item.button_status()
        self.assertEqual(button_status["text"], "Pre-orders Sold Out")
        self.assertEqual(button_status["enabled"], False)

        self.assertEqual(line.status_text, "1 will be preordered")

        # Act
        line.cart.submit()

        # Assert
        self.assertEqual(line.status_text, "Submitted", "Text after submit")


class FilterDistributorStockTest(TestCase):
    def setUp(self):
        self.partner = Partner.objects.create(name="Test Partner", slug="test-partner")
        self.distributor = Distributor.objects.create(dist_name="Hobbytyme", currency='USD')
        self.publisher = Publisher.objects.create(name="Test Publisher")
        self.publisher.available_through_distributors.add(self.distributor)

        self.product_in_stock = Product.objects.create(name="In Stock Product", barcode="12345",
                                                       publisher=self.publisher)
        self.item_in_stock = InventoryItem.objects.create(product=self.product_in_stock, partner=self.partner,
                                                          price=Money(10, "USD"), default_price=Money(10, "USD"))

        self.product_out_of_stock = Product.objects.create(name="Out of Stock Product", barcode="67890",
                                                           publisher=self.publisher)
        self.item_out_of_stock = InventoryItem.objects.create(product=self.product_out_of_stock, partner=self.partner,
                                                              price=Money(10, "USD"), default_price=Money(10, "USD"))

        self.dist_item_in_stock = DistItem.objects.create(distributor=self.distributor, dist_barcode="OTHER1",
                                                          dist_number="D12345", in_stock=True,
                                                          product=self.product_in_stock)
        self.dist_item_out_of_stock = DistItem.objects.create(distributor=self.distributor, dist_barcode="OTHER2",
                                                              dist_number="D67890", in_stock=False,
                                                              product=self.product_out_of_stock)

        self.inventory_file = DistributorInventoryFile.objects.create(distributor=self.distributor,
                                                                      update_date=datetime.datetime.now())
        DistributorInventoryLine.objects.create(inventory_file=self.inventory_file, dist_item=self.dist_item_in_stock,
                                                in_stock=True)
        DistributorInventoryLine.objects.create(inventory_file=self.inventory_file, dist_item=self.dist_item_out_of_stock,
                                                in_stock=False)

    def test_filter_in_stock_at_distributor(self):
        # When filter is off, both items are returned
        items = item_list_filter(managing_partner=self.partner)
        self.assertEqual(items.count(), 2)

        # When filter is on, only the in-stock item is returned
        items = item_list_filter(managing_partner=self.partner, distributor=self.distributor,
                                 in_stock_at_distributor=True)
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.first().product, self.product_in_stock)

    def test_filter_in_stock_at_distributor_default_hobbytyme(self):
        # If no distributor is selected, it should default to Hobbytyme
        items = item_list_filter(managing_partner=self.partner, in_stock_at_distributor=True)
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.first().product, self.product_in_stock)
