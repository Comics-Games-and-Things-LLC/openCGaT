import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

from django.test import SimpleTestCase
from moneyed import Money


class CogsCurrencyTests(SimpleTestCase):
    def test_inventory_costs_are_treated_as_usd(self):
        with patch('partner.models.Partner.objects.get'):
            cogs = importlib.import_module('inventory_report.management.commands.GetCogs')

        po_line = SimpleNamespace(actual_cost=Money(10, 'EUR'), received_quantity=2, remaining_quantity=1)
        po = SimpleNamespace(lines=SimpleNamespace(all=lambda: [po_line]))
        product = SimpleNamespace(barcode='123', name='Product', msrp=Money(20, 'GBP'))
        items = [SimpleNamespace(product=product, current_inventory=2),
                 SimpleNamespace(product=product, current_inventory=1)]
        latest = MagicMock()
        latest.order_by.return_value.first.side_effect = [SimpleNamespace(cost_per_item=Money(5, 'EUR')), None]
        logs = []
        with patch.object(cogs.PurchaseOrder.objects, 'filter', return_value=[po]), \
             patch.object(cogs.Cart.submitted, 'filter') as carts, \
             patch.object(cogs.InventoryItem.objects, 'filter', return_value=items), \
             patch.object(cogs.POLine.objects, 'filter', return_value=latest), \
             patch.object(cogs, 'mark_previous_items_as_sold'), \
             patch.object(cogs, 'email_report'), patch.object(cogs, 'tqdm', side_effect=lambda x, **kw: x), \
             patch.object(cogs, 'log', side_effect=lambda f, message: logs.append(message)), \
             patch.object(cogs, 'open', mock_open(), create=True):
            carts.return_value.filter.return_value.order_by.return_value = []
            cogs.handle_get_cogs(2025)

        self.assertIn(f'Remaining Inventory cost estimate {Money(22, "USD")}', logs)
        self.assertIn(f'{Money(20, "USD")} of inventory was purchased in 2025', logs)
        self.assertTrue(any(str(Money(10, 'USD')) in message and 'according to purchase orders' in message for message in logs))

    def test_inventory_report_cost_is_treated_as_usd(self):
        with patch('partner.models.Partner.objects.get'):
            cogs = importlib.import_module('inventory_report.management.commands.GetCogs')

        report_line = SimpleNamespace(barcode=None)
        report = MagicMock()
        report.report_lines.all.return_value.order_by.return_value = [report_line]
        purchase_line = SimpleNamespace(po='PO', actual_cost=Money(7, 'EUR'))
        logs = []
        with patch.object(cogs.PurchaseOrder.objects, 'filter', return_value=[]), \
             patch.object(cogs.Cart.submitted, 'filter') as carts, \
             patch.object(cogs.InventoryReport.objects, 'order_by') as reports, \
             patch.object(cogs, 'get_purchased_as_line', return_value=purchase_line), \
             patch.object(cogs, 'mark_previous_items_as_sold'), patch.object(cogs, 'email_report'), \
             patch.object(cogs, 'tqdm', side_effect=lambda x, **kw: x), \
             patch.object(cogs, 'log', side_effect=lambda f, message: logs.append(message)), \
             patch.object(cogs, 'open', mock_open(), create=True):
            carts.return_value.filter.return_value.order_by.return_value = []
            reports.return_value.first.return_value = report
            cogs.handle_get_cogs(2025, have_inv_report=True)

        self.assertIn(f'Inventory from the inventory report costs {Money(7, "USD")} ', logs)
