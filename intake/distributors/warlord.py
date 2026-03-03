import traceback
from _decimal import ROUND_UP

import pandas
from django.utils.text import slugify

from game_info.models import Game
from intake.distributors.common import create_valhalla_item
from intake.distributors.utility import log
from intake.models import *
from shop.models import Product, Publisher

dist_name = "Warlord Games"

game_names = [
    "Hail Caesar",
    "Black Powder Epic Battles",
    "Black Powder",
    "Black Seas",
    "Pike & Shotte",
    "Konfikt 47",
    "Warlords of Erehwon",
    "Mythic Americas",
    "Bolt Action",
    "Achtung Panzer",
    "Blood Red Skies",
    "Cruel Seas",
    "Victory at Sea",
]


def import_records():
    distributor = Distributor.objects.get_or_create(dist_name=dist_name)[0]

    publisher, _ = Publisher.objects.get_or_create(name=dist_name)

    file = pandas.ExcelFile('./intake/inventories/Warlord Games USD Order Form March 2026.xlsx')

    log_file = open(f"reports/valhalla_inventory_price_adjustments_warlord_{datetime.today()}.txt", "a")
    log(log_file, "Updating Warlord Prices \n")

    for sheet_name in ["Historical Range","WWII Range", "K47 Sci-Fi & Fantasy Range"]:
        import_from_tab(file, sheet_name, log_file, distributor, publisher)

def import_from_tab(file, sheet_name, log_file, distributor, publisher):
    dataframe = pandas.read_excel(file, sheet_name=sheet_name)
    current_game = None
    records = dataframe.astype('string').to_dict(orient='records')
    for row in records:
        if row.get("Product code ") is None:
            continue
        if row.get("Product code ").strip() in game_names:
            current_game, _ = Game.objects.get_or_create(name=row.get("Product code ").strip())
            continue
        try:  # Skip rows where we can't get the MSRP.
            msrp = row.get("MSRP")
            if not Decimal(msrp):
                continue
            # print(row)
        except Exception:
            continue
        try:
            name = row.get("Product ")
            barcode = row.get('Barcode')
            msrp = Money(msrp, currency='USD')
            mapp = Money(row.get("MAP"), currency='USD')
            if barcode and barcode.strip() != '' and name and name.strip() != '':
                print(name)
                DistItem.objects.filter(distributor=distributor, dist_barcode=barcode).delete()
                item, created = DistItem.objects.get_or_create(
                    distributor=distributor,
                    dist_barcode=barcode,
                    dist_number=row.get("Product code "),
                )
                item.dist_name = name
                item.dist_barcode = barcode
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
                    product, created = Product.objects.get_or_create(
                        barcode=barcode,
                        defaults={'all_retail': True,
                                  'release_date': datetime.today(),
                                  'name': name}
                    )
                product.name = name
                product.publisher = publisher
                product.msrp = msrp
                product.map = mapp
                product.publisher_sku = item.dist_number
                product.all_retail = True
                product.games.add(current_game)
                if not product.description:
                    product.description = row.get("Product format")
                product.save()
                our_price = Money(
                    Decimal(Decimal(85) / Decimal(100) * msrp.amount).quantize(
                        Decimal('.01'), rounding=ROUND_UP),
                    'USD', decimal_places=2)
                create_valhalla_item(product, price=our_price, f=log_file)

        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values")
