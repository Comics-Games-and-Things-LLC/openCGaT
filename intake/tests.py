import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile
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

    @patch("openCGaT.management_util.EmailMessage")
    def test_import_records_us_price_adjustment_file(self, mock_email):
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

        with patch("pandas.ExcelFile") as mock_excel_file, patch("pandas.read_excel", return_value=df) as mock_read_excel, patch("os.listdir", return_value=["US Price Adjustment File - 09.08.xlsx"]), patch("os.path.exists", return_value=True):
            games_workshop.import_records()
            mock_read_excel.assert_called_once()
            _, kwargs = mock_read_excel.call_args
            self.assertEqual(kwargs.get("sheet_name"), "USD Pricelist")
            self.assertEqual(kwargs.get("header"), 3)

        product.refresh_from_db()
        self.assertEqual(product.msrp, Money(Decimal("65.00"), "USD"))

    def test_get_pack_quantity_from_name(self):
        from intake.distributors.games_workshop import get_pack_quantity_from_name
        self.assertEqual(get_pack_quantity_from_name("Base: Abaddon Black (6PK)"), 6)
        self.assertEqual(get_pack_quantity_from_name("Layer: Auric Armour Gold (6-pack)"), 6)
        self.assertEqual(get_pack_quantity_from_name("Citadel Shade: Nuln Oil 6 PK"), 6)
        self.assertEqual(get_pack_quantity_from_name("Contrast Paint: Flesh Tearers Red (6-pk)"), 6)
        self.assertEqual(get_pack_quantity_from_name("Contrast Paint Medium 6 pack"), 6)
        self.assertEqual(get_pack_quantity_from_name("Technical Paint 6pk"), 6)
        self.assertEqual(get_pack_quantity_from_name("Spray Paint (3PK)"), 3)
        self.assertEqual(get_pack_quantity_from_name("Dice Set (12-pack)"), 12)
        self.assertEqual(get_pack_quantity_from_name("Pack of 4 Markers"), 4)
        self.assertIsNone(get_pack_quantity_from_name("Space Marine Backpack"))
        self.assertIsNone(get_pack_quantity_from_name("Jetpack Assault Squad"))
        self.assertIsNone(get_pack_quantity_from_name("Space Marine Intercessors"))
        self.assertIsNone(get_pack_quantity_from_name(None))

    @patch("openCGaT.management_util.EmailMessage")
    def test_import_records_pack_quantity_price_division_and_barcode_retention(self, mock_email):
        import pandas as pd
        publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
        product = Product.objects.create(
            name="Base: Abaddon Black",
            barcode="5011921000001",
            publisher=publisher,
            publisher_short_sku="28-01",
            msrp=Money(Decimal("4.00"), "USD"),
            map=Money(Decimal("3.40"), "USD"),
            release_date=datetime.date.today(),
        )

        df = pd.DataFrame([
            {
                "Description": "Base: Abaddon Black (6PK)",
                "Short Code": "28-01",
                "Barcode": "5011921999999",
                "New US Retail Price": 27.00,
                "New US Trade Price": 13.50,
            }
        ])

        with patch("pandas.ExcelFile"), patch("pandas.read_excel", return_value=df), patch("os.listdir", return_value=["USA PRICE RISE.xlsx"]), patch("os.path.exists", return_value=True):
            games_workshop.import_records()

        product.refresh_from_db()
        # Barcode must NOT be updated to the 6PK barcode (5011921999999)
        self.assertEqual(product.barcode, "5011921000001")
        # MSRP should be divided by quantity (27.00 / 6 = 4.50)
        self.assertEqual(product.msrp, Money(Decimal("4.50"), "USD"))
        # MAP should be 85% of divided MSRP (4.50 * 0.85 = 3.825 -> 3.83)
        self.assertEqual(product.map, Money(Decimal("3.83"), "USD"))

        distributor = Distributor.objects.get(dist_name="Games Workshop")
        dist_item = DistItem.objects.get(distributor=distributor, dist_barcode="5011921999999")
        self.assertEqual(dist_item.quantity_per_pack, 6)
        self.assertEqual(dist_item.product, product)
        self.assertEqual(dist_item.msrp, Money(Decimal("4.50"), "USD"))
        self.assertEqual(dist_item.dist_price, Money(Decimal("2.25"), "USD"))

    @patch("openCGaT.management_util.EmailMessage")
    def test_import_records_pack_quantity_variations(self, mock_email):
        import pandas as pd
        publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
        product = Product.objects.create(
            name="Citadel Spray: Chaos Black",
            barcode=None,
            publisher=publisher,
            publisher_short_sku="65-01",
            msrp=Money(Decimal("18.00"), "USD"),
            map=Money(Decimal("15.30"), "USD"),
            release_date=datetime.date.today(),
        )

        df = pd.DataFrame([
            {
                "Description": "Citadel Spray: Chaos Black (3-pack)",
                "Short Code": "65-01",
                "Barcode": "5011921888888",
                "New US Retail Price": 60.00,
            }
        ])

        with patch("pandas.ExcelFile"), patch("pandas.read_excel", return_value=df), patch("os.listdir", return_value=["USA PRICE RISE.xlsx"]), patch("os.path.exists", return_value=True):
            games_workshop.import_records()

        product.refresh_from_db()
        # Product barcode should remain None (not updated to 3-pack barcode)
        self.assertIsNone(product.barcode)
        # MSRP divided by 3 (60.00 / 3 = 20.00)
        self.assertEqual(product.msrp, Money(Decimal("20.00"), "USD"))
        self.assertEqual(product.map, Money(Decimal("17.00"), "USD"))

    def test_read_new_release_summary_pack_quantity(self):
        import io
        import pandas as pd
        distributor = Distributor.objects.get_or_create(dist_name="Games Workshop")[0]
        partner = Partner.objects.create(name="Valhalla Hobby", slug="valhalla-hobby")

        df = pd.DataFrame([
            {
                "Product Name": "Contrast: Baal Red (6PK)",
                "Short Sales Code": "29-01",
                "Complete Barcode": "5011921777777",
                "US/$": 36.00,
                "Global Pack Code": "99189960001",
                "Format": "Single",
                "Release Date": None,
                "Order From": None,
            }
        ])
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)

        inv_file = DistributorInventoryFile.objects.create(
            distributor=distributor,
            file=SimpleUploadedFile("new_releases.xlsx", excel_buffer.read()),
        )

        games_workshop.read_new_release_summary(inv_file)

        product = Product.objects.get(publisher_short_sku="29-01")
        # Barcode must not be set to the 6PK barcode
        self.assertIsNone(product.barcode)
        # MSRP should be 36.00 / 6 = 6.00
        self.assertEqual(product.msrp, Money(Decimal("6.00"), "USD"))
        self.assertEqual(product.map, Money(Decimal("5.10"), "USD"))

        dist_item = DistItem.objects.get(distributor=distributor, dist_barcode="5011921777777")
        self.assertEqual(dist_item.quantity_per_pack, 6)
        self.assertEqual(dist_item.product, product)
