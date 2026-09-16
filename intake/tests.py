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
from intake.distributors import acd, games_workshop
from intake.management.commands.RunIntakeTasks import Command as RunIntakeTasksCommand
from intake.models import (
    Distributor,
    DistributorWarehouse,
    DistItem,
    DistributorInventoryFile,
    DistributorInventoryLine,
    ItemWarehouseAvailability,
)
from shop.models import Product, Publisher
from game_info.models import Game

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


class GamesWorkshopTestCase(TestCase):
    def test_update_product_information(self):
        publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
        game, _ = Game.objects.get_or_create(name="Warhammer 40k")
        faction, _ = game.factions.get_or_create(name="Space Marines")
        product = Product.objects.create(name="Space Marine Intercessors", barcode="5011921123456",
                                         release_date=datetime.date.today())

        msrp = Money(Decimal("60.00"), "USD")
        maprice = Money(Decimal("51.00"), "USD")
        short_code = "48-75"
        sku = "99120101190"

        games_workshop.update_product_information(
            factions=[faction],
            games=[game],
            maprice=maprice,
            msrp=msrp,
            product=product,
            publisher=publisher,
            short_code=short_code,
            sku=sku,
        )

        product.refresh_from_db()
        self.assertEqual(product.publisher, publisher)
        self.assertEqual(product.publisher_short_sku, short_code)
        self.assertEqual(product.publisher_sku, sku)
        self.assertEqual(product.msrp, msrp)
        self.assertEqual(product.map, maprice)
        self.assertTrue(product.all_retail)
        self.assertFalse(product.page_is_draft)
        self.assertIn(game, product.games.all())
        self.assertIn(faction, product.factions.all())

    def test_update_product_information_with_short_code_alone(self):
        publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
        game, _ = Game.objects.get_or_create(name="Warhammer 40k")
        faction, _ = game.factions.get_or_create(name="Space Marines")
        product = Product.objects.create(
            name="Space Marine Intercessors",
            barcode="5011921123456",
            publisher=publisher,
            publisher_sku="99120101190",
            publisher_short_sku="48-75",
            msrp=Money(Decimal("60.00"), "USD"),
            map=Money(Decimal("51.00"), "USD"),
            release_date=datetime.date.today(),
        )
        product.games.add(game)
        product.factions.add(faction)

        new_msrp = Money(Decimal("65.00"), "USD")
        new_map = Money(Decimal("55.25"), "USD")

        games_workshop.update_product_information(
            factions=[],
            games=[],
            maprice=new_map,
            msrp=new_msrp,
            product=product,
            publisher=publisher,
            short_code="48-75",
            sku=None,
        )

        product.refresh_from_db()
        self.assertEqual(product.msrp, new_msrp)
        self.assertEqual(product.map, new_map)
        self.assertEqual(product.publisher_sku, "99120101190")
        self.assertEqual(product.publisher_short_sku, "48-75")
        self.assertIn(game, product.games.all())
        self.assertIn(faction, product.factions.all())

    def test_get_product_information_from_product_code_handles_none_and_invalid(self):
        self.assertEqual(games_workshop.get_product_information_from_product_code(None), ([], [], []))
        self.assertEqual(games_workshop.get_product_information_from_product_code(""), ([], [], []))
        self.assertEqual(games_workshop.get_product_information_from_product_code("123"), ([], [], []))

    @patch("openCGaT.management_util.EmailMessage")
    def test_import_records_updates_msrp_by_short_code_alone(self, mock_email):
        import pandas as pd
        publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
        product = Product.objects.create(
            name="Space Marine Intercessors",
            barcode="5011921123456",
            publisher=publisher,
            publisher_short_sku="48-75",
            msrp=Money(Decimal("60.00"), "USD"),
            map=Money(Decimal("51.00"), "USD"),
            release_date=datetime.date.today(),
        )

        df = pd.DataFrame([
            {
                "Short Code": "48-75",
                "New US Retail Price": 65.00,
            }
        ])

        with patch("pandas.ExcelFile"), patch("pandas.read_excel", return_value=df), patch("os.listdir", return_value=["USA PRICE RISE.xlsx"]), patch("os.path.exists", return_value=True):
            games_workshop.import_records()

        product.refresh_from_db()
        self.assertEqual(product.msrp, Money(Decimal("65.00"), "USD"))
        self.assertEqual(product.map, Money(Decimal("55.25"), "USD"))
        self.assertFalse(product.page_is_draft)

        distributor = Distributor.objects.get(dist_name="Games Workshop")
        dist_item = DistItem.objects.get(distributor=distributor, dist_number="48-75")
        self.assertEqual(dist_item.msrp, Money(Decimal("65.00"), "USD"))
        self.assertEqual(dist_item.product, product)
