import datetime
import traceback
from _decimal import Decimal, ROUND_UP

import pandas
from django.utils.text import slugify
from djmoney.money import Money

from intake.distributors.common import create_valhalla_item
from intake.distributors.utility import log
from intake.models import Distributor, DistItem
from openCGaT.management_util import email_report
from shop.models import Product, Publisher

dist_name = "Huge Miniatures"


def import_records():
    distributor = Distributor.objects.get_or_create(dist_name=dist_name)[0]

    publisher, _ = Publisher.objects.get_or_create(name="Huge Miniatures")

    file = pandas.ExcelFile('./intake/inventories/2026-04-15-HUGEMINIS-CATALOG.xlsx')
    dataframe = pandas.read_excel(file, sheet_name='CATALOG', header=1)
    product_name_column = "PRODUCT"

    log_file = open(f"reports/valhalla_inventory_price_adjustments_huge_{datetime.datetime.today()}.txt", "a")
    log(log_file, "Updating huge Prices \n")
    price_adjustment_csv = open(f"reports/valhalla_inventory_price_adjustments_huge_{datetime.datetime.now()}.csv", "w")

    records = dataframe.astype('string').to_dict(orient='records')
    for row in records:
        try:  # Skip rows where we can't get the MSRP.
            msrp = row.get('MSRP')
            if not Decimal(msrp):
                continue
            # print(row)
        except Exception:
            continue
        try:
            name = row.get(product_name_column, "")
            category = row.get('CATEGORY',"")
            name = "Huge " + category + " - " + name
            barcode = row.get('UPC')
            if "." in barcode:
                barcode = barcode.split('.')[0]
            msrp = Money(row.get('MSRP'), currency='USD')
            if barcode and barcode.strip() != '' and name and name.strip() != '':
                print(name)
                DistItem.objects.filter(distributor=distributor, dist_barcode=barcode).delete()
                item, created = DistItem.objects.get_or_create(
                    distributor=distributor,
                    dist_barcode=barcode,
                    dist_number=row.get('SKU'),
                )
                item.dist_name = name
                item.dist_barcode = barcode
                item.msrp = msrp
                item.save()

                try:
                    product = Product.objects.get(barcode=barcode)
                except Product.DoesNotExist:
                    try:
                        # First check for items with the same name as the new product
                        product = Product.objects.get(slug=slugify(name))
                        if product.barcode != barcode:
                            potential_existing_product = Product.objects.filter(barcode=barcode)
                            if potential_existing_product.exists():
                                log(log_file,
                                    "Couldn't create {} because it now has barcode {}, but {} already has that barcode".format(
                                        name, barcode, potential_existing_product.first().name
                                    ))
                                continue
                            old_barcode = product.barcode
                            log(log_file,
                                "{} had barcode {} and now has barcode {}, but we did not update the barcode in case we had it in stock".format(
                                    product.name, old_barcode, barcode))
                    except Product.DoesNotExist:
                        product, created = Product.objects.get_or_create(
                            barcode=barcode,
                            defaults={'all_retail': True,
                                      'release_date': datetime.datetime.today(),
                                      'name': name}
                        )
                product.publisher = publisher
                product.msrp = msrp
                product.publisher_sku = item.dist_number
                product.all_retail = True
                product.save()
                create_valhalla_item(product, f=log_file, price_adjustment_csv=price_adjustment_csv)

        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values")

    log_file.flush()
    price_adjustment_csv.flush()
    email_report("huge Price Adjustments", [log_file.name, price_adjustment_csv.name])
