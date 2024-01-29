import csv
import datetime

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.urls import reverse

from checkout.models import Cart
from inventory_report.models import InventoryReport
from partner.models import Partner
from shop.models import Product, InventoryItem


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)

    def handle(self, *args, **options):
        year = options.pop('year')  # Last year by default
        partner = Partner.objects.get(name__icontains="Valhalla")

        if year is None:
            year = datetime.date.today().year - 1

        f2 = open(f"reports/Inventory Mismatches for {year} entries.csv", "w")
        entries_writer = csv.DictWriter(f2, ["Product", "PO Count", "Sold Count", "Inventory Report Count",
                                             "Off by",
                                             "Resolved?",
                                             "Off by (all time)",
                                             "Current Inventory",
                                             f"Sold Since {year}",
                                             f"Bought Since {year}",
                                             "Barcode",
                                             "POs", "Carts"
                                             ])
        entries_writer.writeheader()

        report = InventoryReport.objects.get(partner=partner, date__year=year + 1)  # Since the report is dated jan 1st

        for product in Product.objects.filter(barcode__isnull=False):
            print(product, product.barcode)
            sold_info = product.get_sold_info(partner)

            if not sold_info:
                continue
            all_cart_lines = sold_info["sales"].filter(  # Extra filtering, because the first number of lines is just
                cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED]).exclude(
                cancelled=True)
            all_po_lines = sold_info["po_lines"]
            cart_lines = all_cart_lines.filter(cart__date_submitted__year__lte=year)
            po_lines = all_po_lines.filter(po__date__year__lte=year)
            x_sold = int(cart_lines.aggregate(sum=Sum("quantity"))['sum'] or 0)
            x_purchased = int(po_lines.aggregate(sum=Sum("received_quantity"))['sum'] or 0)

            count_from_inventory_report = report.report_lines.filter(barcode=product.barcode).count()

            sold_after = int(all_cart_lines.filter(cart__date_submitted__year__gt=year)
                             .aggregate(sum=Sum("quantity"))['sum'] or 0)
            bought_after = int(all_po_lines.filter(po__date__year__gt=year)
                               .aggregate(sum=Sum("received_quantity"))['sum'] or 0)

            current_inventory = int(InventoryItem.objects.filter(product=product, partner=partner)
                                    .aggregate(sum=Sum("current_inventory"))['sum'] or 0)

            report_discrepancy = x_purchased - x_sold - count_from_inventory_report

            current_discrepancy = x_purchased + bought_after - x_sold - sold_after - current_inventory

            if report_discrepancy != 0 or current_discrepancy != 0:
                print(f"\tPurchased: {x_purchased}, ", po_lines)
                print(f"\tSold: {x_sold}, ", cart_lines)
                print(f"\tOn inventory report: {count_from_inventory_report}")
                link = "https://valhallahobby.com" + reverse('manage_product', kwargs={'partner_slug': partner.slug,
                                                                                       'product_slug': product.slug})

                entries_writer.writerow({"Product": f'=HYPERLINK("{link}","{str(product)}")',
                                         "PO Count": x_purchased,
                                         "Sold Count": x_sold,
                                         "Inventory Report Count": count_from_inventory_report,
                                         "Off by": report_discrepancy,
                                         "Off by (all time)": current_discrepancy,
                                         "Barcode": product.barcode,
                                         "Current Inventory": current_inventory,
                                         f"Sold Since {year}": sold_after,
                                         f"Bought Since {year}": bought_after,
                                         "POs": " | ".join([str(po_line.po) for po_line in all_po_lines]),
                                         "Carts": " | ".join([str(cart_line.cart) for cart_line in all_cart_lines]),
                                         })
