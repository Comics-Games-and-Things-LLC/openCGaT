import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from django.contrib.auth import get_user_model
from django.urls import reverse

from partner.models import Partner
from intake.distributors import acd
from intake.management.commands.RunIntakeTasks import Command as RunIntakeTasksCommand
from intake.models import (
    Distributor,
    DistributorWarehouse,
    DistItem,
    DistributorInventoryFile,
    DistributorInventoryLine,
    ItemWarehouseAvailability,
)
from shop.models import Product

SAMPLE_ACD_HTML = """<!DOCTYPE html>
<html>
<head><title>Middleton Inventory</title></head>
<body>
<table>
<tr><td colspan="8"><b>9/13/2026 8:00:18 AM</b></td></tr>
<tr><td colspan="8">Middleton Inventory</td></tr>
<tr>
  <th>ItemID</th>
  <th>ShortDesc</th>
  <th>MSRP</th>
  <th>Product Type</th>
  <th>Status</th>
  <th>Street Date</th>
  <th>UPC</th>
  <th>MIDDLETON</th>
</tr>
<tr>
  <td>25C100000</td>
  <td>Beer Mug Dice</td>
  <td>25.00</td>
  <td>NPI</td>
  <td>Active</td>
  <td>10/00/25 EST</td>
  <td>850037822942</td>
  <td>Yes</td>
</tr>
<tr>
  <td>3D680004</td>
  <td>Dragon Shield Sleeves</td>
  <td>12.99</td>
  <td>Standard</td>
  <td>Active</td>
  <td></td>
  <td>5706569800040</td>
  <td></td>
</tr>
</table>
</body>
</html>
"""


class ACDInventoryTestCase(TestCase):
    def setUp(self):
        self.distributor, _ = Distributor.objects.get_or_create(dist_name="ACD")

    @patch("intake.distributors.acd.requests.get")
    def test_acd_update_inventory(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_ACD_HTML.encode("utf-8")
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Create a product matching item1 by barcode
        product1 = Product.objects.create(name="Beer Mug Dice", barcode="850037822942")

        inv_file = acd.update_inventory()

        self.assertIsNotNone(inv_file)
        self.assertEqual(inv_file.distributor, self.distributor)
        self.assertEqual(inv_file.warehouse.warehouse_name, "Middleton")
        self.assertTrue(inv_file.processed)
        self.assertEqual(inv_file.line_count, 2)

        # Check DistItems
        item1 = DistItem.objects.get(distributor=self.distributor, dist_number="25C100000")
        self.assertEqual(item1.product, product1)
        self.assertEqual(item1.dist_name, "Beer Mug Dice")
        self.assertEqual(item1.msrp, Money(Decimal("25.00"), "USD"))
        # 25.00 * (1 - 0.47) = 13.25
        self.assertEqual(item1.dist_price, Money(Decimal("13.25"), "USD"))
        self.assertEqual(item1.dist_barcode, "850037822942")
        self.assertEqual(item1.expected, datetime.date(2025, 10, 1))
        self.assertTrue(item1.in_stock)

        item2 = DistItem.objects.get(distributor=self.distributor, dist_number="3D680004")
        self.assertEqual(item2.dist_name, "Dragon Shield Sleeves")
        self.assertEqual(item2.msrp, Money(Decimal("12.99"), "USD"))
        self.assertIsNone(item2.dist_price)
        self.assertEqual(item2.dist_barcode, "5706569800040")
        self.assertIsNone(item2.expected)
        self.assertIsNone(item2.in_stock)

        # Check ItemWarehouseAvailability
        avail1 = ItemWarehouseAvailability.objects.get(dist_item=item1, warehouse=inv_file.warehouse)
        self.assertTrue(avail1.in_stock)

        # Check DistributorInventoryLine
        lines = DistributorInventoryLine.objects.filter(inventory_file=inv_file)
        self.assertEqual(lines.count(), 2)

    @patch("intake.distributors.acd.requests.get")
    def test_update_acd_inventory_command(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = SAMPLE_ACD_HTML.encode("utf-8")
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        call_command("update_acd_inventory")
        self.assertTrue(DistributorInventoryFile.objects.filter(distributor=self.distributor).exists())

    @patch("intake.management.commands.RunIntakeTasks.call_command")
    def test_run_intake_tasks_acd_inventory(self, mock_call_command):
        # No existing inventory file -> should call update_acd_inventory
        RunIntakeTasksCommand.recurring_logic()
        mock_call_command.assert_any_call("update_acd_inventory")

        mock_call_command.reset_mock()
        # With fresh inventory file -> should not call update_acd_inventory
        DistributorInventoryFile.objects.create(
            distributor=self.distributor,
            update_date=timezone.now(),
            processed=True,
        )
        RunIntakeTasksCommand.recurring_logic()
        calls = [c[0][0] for c in mock_call_command.call_args_list]
        self.assertNotIn("update_acd_inventory", calls)


class IntakeDistItemsTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="admin", password="password")
        self.partner = Partner.objects.create(name="Test Partner", slug="test-partner")
        self.partner.administrators.add(self.user)
        self.distributor = Distributor.objects.create(dist_name="ACD")
        self.client.force_login(self.user)

    def test_intake_view_loads_dist_records_by_product(self):
        product = Product.objects.create(name="Awesome Board Game", barcode="123456789012")
        dist_item = DistItem.objects.create(
            distributor=self.distributor,
            dist_number="ABG-001",
            dist_name="Awesome Board Game (Dist)",
            msrp=Money(Decimal("49.99"), "USD"),
            map=Money(Decimal("39.99"), "USD"),
            product=product,
            dist_barcode="different-or-none"
        )

        response = self.client.get(
            reverse("intake_item", kwargs={"partner_slug": self.partner.slug, "barcode": "123456789012"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("dist_items", response.context)
        self.assertIn(dist_item, response.context["dist_items"])
        self.assertContains(response, "Awesome Board Game (Dist)")
        self.assertContains(response, "Distributor Records:")
        self.assertContains(response, "$49.99")
