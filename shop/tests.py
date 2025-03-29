import datetime

from django.contrib.sites.models import Site
from django.test import TestCase
from djmoney.money import Money

from checkout.models import Cart
from partner.models import Partner
from shop.models import Product, InventoryItem


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
