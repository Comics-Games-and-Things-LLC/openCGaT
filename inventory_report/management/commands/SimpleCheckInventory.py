import csv
import datetime

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.urls import reverse

from checkout.models import Cart
from inventory_report.models import InventoryReport
from openCGaT.management_util import email_report
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

        filename = f"reports/Simple Inventory Mismatches for {year} entries.csv"
        f2 = open(filename, "w")
        entries_writer = csv.DictWriter(f2, ["Product", "Log Count", "Inventory Report Count",
                                             "Off by",
                                             "Resolved?",
                                             "Current Inventory",
                                             f"Sold Since {year}",
                                             f"Bought Since {year}",
                                             "Barcode",
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
            inventory_item = InventoryItem.objects.filter(product=product, partner=partner).first()
            count_from_log = 0
            if inventory_item:
                last_log = inventory_item.inv_log.filter(timestamp__year__lte=year).order_by('-timestamp').first()
                if last_log:
                    count_from_log = last_log.after_quantity or 0

            sold_after = int(all_cart_lines.filter(cart__date_submitted__year__gt=year)
                             .aggregate(sum=Sum("quantity"))['sum'] or 0)
            bought_after = int(all_po_lines.filter(po__date__year__gt=year)
                               .aggregate(sum=Sum("received_quantity"))['sum'] or 0)

            current_inventory = int(InventoryItem.objects.filter(product=product, partner=partner)
                                    .aggregate(sum=Sum("current_inventory"))['sum'] or 0)

            report_discrepancy = count_from_log - count_from_inventory_report


            if report_discrepancy != 0:
                print(f"\tCount from log: {count_from_log}")
                print(f"\tOn inventory report: {count_from_inventory_report}")
                link = "https://valhallahobby.com" + reverse('manage_product', kwargs={'partner_slug': partner.slug,
                                                                                       'product_slug': product.slug})

                entries_writer.writerow({"Product": f'=HYPERLINK("{link}","{str(product)}")',
                                         "Log Count": count_from_log,
                                         "Inventory Report Count": count_from_inventory_report,
                                         "Off by": report_discrepancy,
                                         "Barcode": product.barcode,
                                         "Current Inventory": current_inventory,
                                         f"Sold Since {year}": sold_after,
                                         f"Bought Since {year}": bought_after,
                                         })
        email_report("Simple Inventory Mismatches", filename)
