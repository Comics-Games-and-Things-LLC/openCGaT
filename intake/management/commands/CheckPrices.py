import csv
import os
import sys
from inspect import getmembers

import pandas
from django.core.management.base import BaseCommand, CommandError

from intake.distributors import alliance, acd, parabellum, wyrd, games_workshop, gw_paints
from intake.distributors.utility import log
from intake.models import *
from shop.models import Publisher


class Command(BaseCommand):
    help = "Checks prices against manufacturer's information"

    def handle(self, *args, **options):

        trade_range_name = ""
        inventories_path = './intake/inventories/'
        for file in os.listdir(inventories_path):
            if "Trade Range" in file or "USA PRICE RISE" in file:
                trade_range_name = file
        if file is None:
            print("Please have a file with 'Trade Range' or 'USA Price Rise' in the inventories folder")
            exit()

        file = pandas.ExcelFile(os.path.join(inventories_path, trade_range_name))
        dataframe = pandas.read_excel(file, header=0, sheet_name='USA', converters={'Product': str, 'Barcode': str})

        records = dataframe.to_dict(orient='records')

        f = open("reports/Price Check.txt", "w")
        csvfile = open("reports/Price Check.csv", "w")
        writer = csv.DictWriter(csvfile, ['Product', 'Current MSRP', 'Current Inventory', 'New MSRP'])
        writer.writeheader()
        log(f, "Price Check for GW")
        all_current_shortcodes = []
        for row in records:
            # print(row)
            product_code = row.get('Product')
            short_code = row.get('Short Code', row.get("SS Code"))
            all_current_shortcodes.append(short_code)
            name = row.get('Description')
            barcode = row.get('Barcode')
            msrp = Money(row.get('US/$ Retail', row.get("USD-NEW MSRP")), currency='USD')
            maprice = msrp * .85

            for product in Product.objects.filter(barcode=barcode):
                if product.msrp != msrp:
                    log(f, f"{product} does not have the correct MSRP:")
                    log(f, f"{product.barcode} should be msrp: {msrp}, map: {maprice}")

            for product in Product.objects.filter(publisher_short_sku=short_code).exclude(barcode=barcode):
                if product.msrp != msrp:
                    log(f, f"{product} does not have the correct MSRP and has an unexpected barcode.")
                    log(f, f"{product.barcode} should be msrp: {msrp}, map: {maprice}")

        publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
        partner = Partner.objects.get(name__icontains="Valhalla")

        for product in Product.objects.filter(publisher=publisher).exclude(page_is_draft=True):
            if product.publisher_short_sku not in all_current_shortcodes:
                log(f, f"{product} does not appear in the current trade range")
                inv_count = product.all_inventory_for_partner(partner)
                writer.writerow({"Product": product.name,
                                 "Current MSRP": product.msrp,
                                 "Current Inventory": inv_count
                                 })
                if inv_count == 0:
                    product.page_is_draft = True
                    product.save()
