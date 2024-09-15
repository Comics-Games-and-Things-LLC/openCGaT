import decimal
import traceback
import urllib.request
from os.path import exists

import pandas

from intake.distributors.common import create_valhalla_item
from intake.models import *
from shop.models import Product, Publisher

dist_name = 'Asmodee'

def import_records():
    distributor = Distributor.objects.get_or_create(dist_name=dist_name)[0]


    timestamp = datetime.today().date().strftime("%Y%m%d")
    filename = "./intake/inventories/Asmodee-{}.csv".format(timestamp)
    if not exists(filename):
        print("Downloading today's Asmodee inventory")
        try:
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            urllib.request.install_opener(opener)
            urllib.request.urlretrieve("https://www.asmodeena.com/active-catalog-csv", filename)
        except urllib.error.HTTPError as e:
            print(e)
            print(e.fp.read())
            exit()
    else:
        print("Using previously downloaded Asmodee inventory")
    dataframe = pandas.read_csv(filename, header=0, encoding='latin1')

    records = dataframe.astype('string').fillna("").to_dict(orient='records')
    for row in records:
        print(row)
        try:
            publisher, _ = Publisher.objects.get_or_create(name=row.get('Studio'))

            rawdate = row.get('Release Date')

            date = datetime(2022, 1, 1)  # Default date to today.
            try:
                if rawdate != '':
                    date = datetime.strptime(rawdate, '%m/%d/%Y').date()
            except ValueError:
                pass

            msrpstring = str(row.get('MSRP')).replace("$", "").strip()
            mapstring = str(row.get('MAP')).replace("$", "").replace("-", "").strip()

            msrp = Money(msrpstring, 'USD')

            maprice = None
            try:
                maprice = Money(mapstring, 'USD')
                if maprice.amount == 0:
                    maprice = 0
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
                    product.msrp = msrp
                    product.map = maprice
                    product.publisher = publisher
                    if rawdate:
                        product.release_date = date
                    product.save()

                    create_valhalla_item(product)

        except Exception as e:
            traceback.print_exc()
            print("Not full line, can't get values; or invalid data")
