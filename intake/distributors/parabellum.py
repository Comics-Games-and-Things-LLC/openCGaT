import traceback
from _decimal import Decimal

import pandas
from django.utils.text import slugify

from game_info.models import Game
from intake.distributors.common import create_valhalla_item
from intake.distributors.utility import log
from intake.models import *
from shop.models import Product, Publisher

dist_name = "Para Bellum Wargames"


def import_records():
    distributor = None
    try:
        Distributor.objects.filter(dist_name="Para Bellum").update(dist_name=dist_name)
    except Exception as e:
        print(e)
        exit()
    try:
        Distributor.objects.get_or_create(dist_name=dist_name)[0]
    except Distributor.MultipleObjectsReturned:
        distributors = Distributor.objects.filter(dist_name__icontains="para")
        distributor = distributors.order_by("id").first()
        print(distributor.id)
        for dist in distributors:
            print(dist.id)
            if dist.id != distributor.id:
                for item in PurchaseOrder.objects.filter(distributor=dist).all():
                    print(item)
                    item.distributor = distributor
                    item.save()
                for item in DistItem.objects.filter(distributor=dist).all():
                    print(item)
                    item.distributor = distributor
                    item.save()
                dist.delete()

    distributor = Distributor.objects.get_or_create(dist_name=dist_name)[0]

    publisher, _ = Publisher.objects.get_or_create(name="Para Bellum Wargames")
    tloak, _ = Game.objects.get_or_create(name="Conquest: The Last Argument of Kings")
    fb, _ = Game.objects.get_or_create(name="Conquest: First Blood")

    file = pandas.ExcelFile('./intake/inventories/UPDATE Conquest Order Form -August 28, 2025.xlsx')
    row_from_excel_with_accurate_headers = 10
    dataframe = pandas.read_excel(file, header=row_from_excel_with_accurate_headers - 1,
                                  sheet_name='WHOLESALE Order Form')
    product_name_column = "Product Name -NEW 2000 point Armies (net pricing)"

    log_file = open(f"reports/valhalla_inventory_price_adjustments_conquest_{datetime.today()}.txt", "a")
    log(log_file, "\n\nUpdating Para Bellum Prices \n")

    # Header is row 10 to skip bundles. Those rows also don't have MSRPS, just Net US.

    records = dataframe.astype('string').to_dict(orient='records')
    for row in records:
        try:  # Skip rows where we can't get the MSRP.
            msrp = row.get('MSRP US$')
            if not Decimal(msrp):
                continue
            # print(row)
        except Exception:
            continue
        try:
            description = "{} \n\n {}".format(row.get('Web Extended Descriptions'), row.get('Contents'))
            weight_oz = row.get('Weight (Gr/Oz)').split("/")[-1]
            try:
                weight = float(weight_oz) / 16
            except Exception:
                weight = None

            name = "Conquest: " + row.get(product_name_column)
            if '(Command' in name:
                name = name.split('(')[0].strip()
            barcode = row.get('Barcode')
            msrp = Money(row.get('MSRP US$'), currency='USD')
            mapp = None
            try:
                mapp = Money(row.get('MAPP US$'), currency='USD')
            except Exception:
                pass  # Couldn't convert MAP
            if barcode and barcode.strip() != '' and name and name.strip() != '':
                print(name)
                DistItem.objects.filter(distributor=distributor, dist_barcode=barcode).delete()
                item, created = DistItem.objects.get_or_create(
                    distributor=distributor,
                    dist_barcode=barcode,
                    dist_number=row.get('SKU #'),
                )
                item.dist_name = name
                item.dist_barcode = barcode
                item.dist_description = description
                item.weight_lbs = weight
                item.msrp = msrp
                item.map = mapp
                item.save()
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
                            "{} had barcode {} and now has barcode {}".format(product.name, old_barcode, barcode))
                        product.barcode = barcode
                        product.all_retail = True
                except Product.DoesNotExist:
                    continue  # Do not make new products right now
                    # product, created = Product.objects.get_or_create(
                    #     barcode=barcode,
                    #     defaults={'all_retail': True,
                    #               'release_date': datetime.today(),
                    #               'description': description,
                    #               'name': name}
                    # )
                # product.name = name
                product.weight = weight
                product.publisher = publisher
                product.msrp = msrp
                product.map = mapp
                product.publisher_sku = item.dist_number
                product.all_retail = True
                product.games.add(tloak, fb)
                product.save()
                create_valhalla_item(product)

        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values")
