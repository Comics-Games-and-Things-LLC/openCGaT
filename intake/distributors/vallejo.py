import time
import traceback
import urllib
from operator import truediv
from os import MFD_ALLOW_SEALING

import pandas
from bs4 import BeautifulSoup
from checkdigit import gs1

from images.models import Image
from intake.distributors import acd
from intake.distributors.common import create_valhalla_item
from intake.models import *
from shop.models import Product, Publisher

dist_name = "Acrylicos Vallejo"
alt_name = "Vallejo"

publisher_name = dist_name

def get_barcode_from_sku(sku):
    barcode_start = "8429551" + sku.replace('.', '')
    last_digit = gs1.calculate(barcode_start)
    return barcode_start + last_digit

def import_records():
    publisher, _ = Publisher.objects.get_or_create(name=dist_name)

    file = pandas.ExcelFile('./intake/inventories/New VMC 6pk boxes.xlsx')
    dataframe = pandas.read_excel(file, header=0)

    records = dataframe.astype('string').fillna("").to_dict(orient='records')
    for row in records:
        try:

            pack_barcode = row.get('Box Barcode')

            number = pack_barcode[-6:-1]
            print(number)
            display_number = f"{number[:2]}.{number[2:]}"
            barcode = get_barcode_from_sku(number)
            print(barcode)
            # Wait 1 second before attempting to ask acd.
            print(f"Asking ACD for the paint {display_number}")

            time.sleep(1)
            name, acd_msrp = acd.get_name_and_msrp(barcode)
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


def download_images():
    products_missing_images = Product.objects.filter(publisher__name=publisher_name, primary_image__isnull=True)
    for product in products_missing_images:
        start_name_index = len("Vallejo ")
        end_name_index = start_name_index + len("XX.XXX")
        paint_code = product.name[start_name_index : end_name_index]
        if not validate_paint_code(paint_code):
            continue
        print(paint_code)
        image_url = get_image_from_website(paint_code)
        if not image_url:
            continue
        print(image_url)
        image = Image.create_from_external_url(image_url)
        print("\t", image)
        product.primary_image = image
        product.attached_images.add(image)
        product.save()


def get_image_from_website(paint_code):

    paint_code_no_dot = paint_code.replace(".","")

    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    urllib.request.install_opener(opener)
    # This works but requests doesn't for some reason.
    print(f"Searching for {paint_code}")
    time.sleep(1) # Wait 1 second so we don't query them too much.
    vallejo_file = urllib.request.urlopen(f"https://acrylicosvallejo.com/en/?s={paint_code}")
    soup = BeautifulSoup(vallejo_file.read(), features="html5lib")
    search_result=None
    for entry in soup.find_all("article", class_="search-entry"):
        link = entry.find_next("a")['href']
        if paint_code_no_dot in link:
            search_result = entry
            break
    if search_result is None:
        return
    image_element = search_result.find_next('img')
    src_set = image_element['srcset'].split(",")
    # Images are in the format " url NNNw"
    # Highest quality image will be the last one.
    image_url = src_set[-1].split(" ")[-2].strip()
    return image_url



def validate_paint_code(code: str ):
    """
    Ensure that a vallejo paint matches the pattern "XX.XXX" Where each x is a digit.
    @param code: Paint code as a string
    @return: True or false if it matches the pattern.
    """
    if not code[2:3] == ".":
        return False
    for digit in (code[0:2] + code[3:6]):
        if not digit.isnumeric():
            return False
    return True