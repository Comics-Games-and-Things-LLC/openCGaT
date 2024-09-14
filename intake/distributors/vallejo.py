import time
import traceback

import pandas
from checkdigit import gs1

from intake.distributors import acd
from intake.distributors.common import create_valhalla_item
from intake.models import *
from shop.models import Product, Publisher


def import_records():
    publisher, _ = Publisher.objects.get_or_create(name="Acrylicos Vallejo")

    file = pandas.ExcelFile('./intake/inventories/New VMC 6pk boxes.xlsx')
    dataframe = pandas.read_excel(file, header=0)

    records = dataframe.astype('string').fillna("").to_dict(orient='records')
    for row in records:
        try:

            pack_barcode = row.get('Box Barcode')

            number = pack_barcode[-6:-1]
            print(number)
            display_number = f"{number[:2]}.{number[2:]}"
            barcode_start = "8429551" + number.replace('.', '')
            last_digit = gs1.calculate(barcode_start)
            barcode = barcode_start + last_digit
            print(barcode)
            # Wait 1 second before attempting to ask acd.
            print(f"Asking ACD for the paint {display_number}")

            time.sleep(1)
            name, acd_msrp = acd.query_for_info(barcode)
            msrp = None
            price = None
            if acd_msrp == "3.99":
                msrp = "3.50"  # Standard Vallejo is 3.50 at hobbytyme, not 3.99
                price = "3.29"  # We want to charge 3.29 at least for now.
            print(f"{name} {barcode} ${acd_msrp}, (which we treat as ${msrp})")
            formatted_name = f"Vallejo {display_number} {name}"
            print(f"\t{formatted_name}")
            if barcode and barcode.strip() != '' and name and name.strip() != '':
                if Product.objects.filter(barcode=barcode).exists():
                    print("\tProduct already exists, skipping creation...\n")
                    continue  # Skip this product if it already exists.
                product = Product.objects.create(
                    all_retail=True,
                    release_date=datetime.today(),
                    barcode=barcode,
                    name=formatted_name,
                    publisher=publisher,
                    msrp=msrp
                )
                product.save()
                create_valhalla_item(product, price)
            print('\n')

        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values; or invalid data")
