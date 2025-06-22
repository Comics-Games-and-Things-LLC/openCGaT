import csv
import decimal
import time

from django.core.management.base import BaseCommand

from intake.distributors.acd import query_for_info
from intake.distributors.utility import log
from intake.models import *


class Command(BaseCommand):
    help = "Checks prices against manufacturer's information"

    def handle(self, *args, **options):

        barcodes = POLine.objects.filter(po__distributor__dist_name="ACD").order_by("-po__date_received").values_list(
            'barcode', flat=True).distinct()
        f = open("reports/Price Check.txt", "w")

        csvfile = open("reports/Price Check.csv", "w")
        writer = csv.DictWriter(csvfile, ['Product', 'Current MSRP', 'Current Inventory', 'New MSRP'])
        writer.writeheader()
        log(f, "Price Check for ACD")
        for barcode in barcodes:
            msrp = None
            time.sleep(1)
            msrp = query_for_info(barcode).get('MSRP')
            if msrp is None:
                continue
            print(f"Success for {barcode}")
            for product in Product.objects.filter(barcode=barcode):
                if not product.msrp:
                    log(f, f"{product} does not have a MSRP set:")
                    log(f, f"\t{product.barcode} should be: {msrp}, is null")

                if abs(product.msrp.amount - msrp) > 0.01:
                    log(f, f"{product} does not have the correct MSRP:")
                    log(f, f"\t{product.barcode} should be: {msrp}, is: {product.msrp.amount}")
