import os
import sys
from inspect import getmembers

import pandas
from django.core.management.base import BaseCommand, CommandError

from intake.distributors import alliance, acd, parabellum, wyrd, games_workshop, gw_paints
from intake.distributors.utility import log
from intake.models import *


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
        log(f, "Price adjustments for Games Workshop 2024")
        for row in records:
            # print(row)
            product_code = row.get('Product')
            short_code = row.get('Short Code', row.get("SS Code"))
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
