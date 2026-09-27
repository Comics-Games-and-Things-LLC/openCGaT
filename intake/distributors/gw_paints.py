import traceback

import pandas

import intake.distributors.games_workshop
from intake.distributors.common import create_valhalla_item
from intake.distributors.utility import remove_barcode_dashes
from intake.models import *
from shop.models import Product, Publisher


def import_records():
    distributor = Distributor.objects.get_or_create(dist_name=intake.distributors.games_workshop.dist_name)[0]
    publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
    category, _ = Category.objects.get_or_create(name="Acrylic Paint")

    file = pandas.ExcelFile('./intake/inventories/Warhammer Tone Pro Codes and Barcodes (individual, JUS).xlsx')
    dataframe = pandas.read_excel(file, header=0, sheet_name='Paint', converters={'Product': str, 'Barcode': str})

    records = dataframe.to_dict(orient='records')
    f = open("reports/products_with_price_adjustments.txt", "a")
    for row in records:
        print(row)
        try:
            short_code = row.get('SSC')
            full_name = row.get('Product Description')

            paint_name = full_name
            if ':' in paint_name:
                paint_name = paint_name.split(':')[-1]
            paint_name = paint_name.split("JUC")[0]
            paint_name = paint_name.strip().title()
            product_name = "Warhammer Tone Pro: {}".format(paint_name)

            sku = row.get('SKU')
            barcode_single = remove_barcode_dashes(row.get('Individual Barcode'))

            existing_products = Product.objects.filter(barcode=barcode_single).order_by('-release_date')
            if existing_products.count() == 1:
                product = existing_products.first()
            else:
                existing_products = Product.objects.filter(name__search=product_name).order_by('-release_date')
                if existing_products.count() == 1:
                    product = existing_products.first()
                else:
                    product, created = Product.objects.get_or_create(barcode=barcode_single, name=product_name)

            print(paint_name, barcode_single)
            product.name = product_name
            product.barcode = barcode_single
            product.release_date = datetime.date(year=2026, month=10, day=24)
            product.msrp = Money(6.75, 'USD')
            product.publisher_short_sku = short_code
            product.publisher_sku = sku
            if not product.description:
                product.description = "Warhammer Tone Pro Paint in 12 ml bottle."

            product.categories.clear()
            product.categories.add(category)
            product.save()

            item = create_valhalla_item(product)
            item.allow_backorder = True
            item.enable_restock_alert = True
            item.low_inventory_alert_threshold = 2
            item.save()


        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values")
