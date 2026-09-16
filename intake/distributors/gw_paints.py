import traceback
import datetime

import requests

import intake.distributors.games_workshop
from game_info.models import Game
from intake.distributors.utility import log, remove_barcode_dashes
from intake.models import *
import pandas
import xlrd

from shop.models import Product, Publisher, InventoryItem


def import_records():
    distributor = Distributor.objects.get_or_create(dist_name=intake.distributors.games_workshop.dist_name)[0]
    publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
    category, _ = Category.objects.get_or_create(name="Acrylic Paint")

    file = pandas.ExcelFile('./intake/inventories/Citadel Paints Bar Codes 07_22.xlsx')
    dataframe = pandas.read_excel(file, header=0, sheet_name='Sheet1', converters={'Product': str, 'Barcode': str})

    records = dataframe.to_dict(orient='records')
    f = open("reports/products_with_price_adjustments.txt", "a")
    for row in records:
        print(row)
        try:
            paint_line_raw = row.get('Range')
            paint_line = paint_line_raw.split('-')[-1].strip()

            short_code = row.get('SSC')
            full_name = row.get('PRODUCT NAME')
            paint_name = full_name
            if ':' in paint_name:
                paint_name = paint_name.split(':')[-1]
            paint_name = paint_name.split("(")[0]
            paint_name = paint_name.strip().title()

            size = row.get('SIZE')
            barcode_6_pack = row.get('Barcode (6-Pack)')
            barcode_single = remove_barcode_dashes(row.get('Barcode (Single)'))
            range_code = row.get("Range 07_22")

            trade_range = None
            if range_code:
                trade_range, _ = TradeRange.objects.get_or_create(code=range_code, distributor=distributor,
                                                                  defaults={'name': range_code})

            is_rerelease = False
            product = None

            product_name = "Citadel {}: {} {}".format(paint_line, paint_name, size)
            existing_products = Product.objects.filter(product_name__search=product_name).order_by('-release_date')
            if existing_products.count() == 1:
                product = existing_products.first()
                if product.barcode is None:
                    is_rerelease = True
            else:
                product, created = Product.objects.get_or_create(barcode=product)

            if is_rerelease:
                product_name = product_name + " (2022)"

            print(paint_name, barcode_single, barcode_6_pack, trade_range.code)
            product.name = product_name
            product.barcode = barcode_single
            product.release_date = datetime.date(year=2022, month=7, day=16)

            product.categories.clear()
            product.categories.add(category)


        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values")
