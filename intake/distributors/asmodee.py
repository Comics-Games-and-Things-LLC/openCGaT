import decimal
import traceback

import pandas

from intake.distributors.common import create_valhalla_item
from intake.models import *
from shop.models import Product

dist_name = 'Asmodee'


def import_records():
    distributor = Distributor.objects.get_or_create(dist_name=dist_name)[0]
    f = open("reports/valhalla_inventory_price_adjustments.txt", "a")
    partner = Partner.objects.get(name__icontains="Valhalla")

    filename = "./intake/inventories/SRP and MAP Increases - 7.1.25.xlsx - Sheet1.csv"
    dataframe = pandas.read_csv(filename, header=0, encoding='latin1')
    records = dataframe.astype('string').fillna("").to_dict(orient='records')
    for row in records:
        # print(row)
        try:

            msrpstring = str(row.get('New SRP')).replace("$", "").strip()
            mapstring = str(row.get('New MAP')).replace("$", "").replace("-", "").strip()

            msrp = Money(msrpstring, 'USD')
            maprice = Money(0, 'USD')
            try:
                maprice = Money(mapstring, 'USD')
            except decimal.InvalidOperation:
                pass

            barcode = row.get('UPC')
            if barcode.find('.') != -1:
                barcode = barcode.split('.')[0]

            if len(barcode) > 3:  # if there's actually a barcode

                DistItem.objects.filter(distributor=distributor,
                                        dist_barcode=barcode).delete()  # Delete existing entries for this distributor
                DistItem.objects.get_or_create(distributor=distributor,
                                               dist_barcode=barcode,
                                               dist_name=row.get('Title'),
                                               dist_number=row.get('SKU'),
                                               msrp=msrp,
                                               map=maprice,
                                               )

                products = Product.objects.filter(barcode=barcode)
                if products.count() == 1:
                    product = products.first()
                    product.all_retail = True
                    old_msrp = product.msrp
                    product.msrp = msrp
                    if maprice.amount == 0:
                        product.map = None
                    else:
                        product.map = maprice
                    product.save()
                    if maprice.amount > 1:
                        new_price = maprice
                    else:
                        new_price = product.get_price_from_rule(partner)
                    create_valhalla_item(product, f=f, price=new_price)


        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values; or invalid data")
            exit()
