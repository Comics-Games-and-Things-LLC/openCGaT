import datetime

from django.core.management.base import BaseCommand
from django.db.models import Sum

from checkout.models import Cart
from inventory_report.models import InventoryReport
from partner.models import Partner
from shop.models import Product


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)

    def handle(self, *args, **options):
        year = options.pop('year')  # Last year by default
        partner = Partner.objects.get(name__icontains="Valhalla")

        if year is None:
            year = datetime.date.today().year - 1

        report = InventoryReport.objects.get(partner=partner, date__year=year + 1)  # Since the report is dated jan 1st

        for product in Product.objects.filter(barcode__isnull=False):
            print(product, product.barcode)
            sold_info = product.get_sold_info(partner)

            if not sold_info:
                continue
            cart_lines = sold_info["sales"].filter(  # Extra filtering, because the first number of lines is just
                cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED]).exclude(
                cancelled=True)
            po_lines = sold_info["po_lines"]
            if year:
                cart_lines = cart_lines.filter(cart__date_submitted__year__lte=year)
                po_lines = po_lines.filter(po__date__year__lte=year)
            x_sold = int(cart_lines.aggregate(sum=Sum("quantity"))['sum'] or 0)
            x_purchased = int(po_lines.aggregate(sum=Sum("received_quantity"))['sum'] or 0)

            count_from_inventory_report = report.report_lines.filter(barcode=product.barcode).count()
            if count_from_inventory_report != x_sold-x_purchased:
                print(f"\tPurchased: {x_purchased}, ", po_lines)
                print(f"\tSold: {x_sold}, ", cart_lines)
                print(f"\tOn inventory report: {count_from_inventory_report}")
                exit()

