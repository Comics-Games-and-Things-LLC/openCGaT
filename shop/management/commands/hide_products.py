import csv
from datetime import datetime

from django.core.management import BaseCommand
from django.db.models import Sum

from intake.distributors.utility import log
from openCGaT.management_util import email_report
from shop.models import Product, Category, InventoryItem


class Command(BaseCommand):
    def handle(self, *args, **options):
        hobby_products, _ = Category.objects.get_or_create(name="Hobby Products")
        hidden_products_log = open(f"reports/hidden_products_{datetime.now()}.txt", "w")
        log_csv = open(f"reports/products_to_consider_hiding{datetime.now()}.csv", "w")
        writer = csv.DictWriter(log_csv, ['Publisher', 'Product', 'Barcode', 'Current Inventory'])
        writer.writeheader()

        # GW has it's own handling. TTCombat and GCT have no MAP.
        exclude_publisher_names = ["Games Workshop", "TTCombat", "GCT Studios"]

        # Find all products not currently draft with no barcode

        for product in Product.objects.exclude(publisher__name__in=exclude_publisher_names) \
                .filter(barcode__isnull=True).exclude(page_is_draft=True):
            count = InventoryItem.objects.filter(product=product).aggregate(sum=Sum("current_inventory"))['sum'] or 0
            writer.writerow({'Publisher': product.publisher,
                             'Product': product.name,
                             'Barcode': product.barcode,
                             'Current Inventory': count})
            if count == 0:
                product.page_is_draft = True
                product.save()
                log(hidden_products_log, f"Hid {product.name}, since there was no stock")

        hidden_products_log.flush()
        log_csv.flush()
        email_report("Hidden Products", [hidden_products_log.name, log_csv.name])
