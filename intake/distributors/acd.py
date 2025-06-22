import decimal
import json
import traceback
from decimal import ROUND_DOWN

import pandas
import requests
from bs4 import BeautifulSoup

from intake.models import *

dist_name = "ACD"
npi = .47


def import_records(dist_inv_file):
    # Download files from b2
    with requests.get(dist_inv_file.file.url) as r:
        file = r.content
        filename = dist_inv_file.file.name.split('/')[-1]

        # For row 0 and column 0
        timestamp = pandas.read_excel(file, header=0).columns.values[0]
        print()

        distributor = Distributor.objects.get_or_create(dist_name=dist_name)[0]
        warehouse = DistributorWarehouse.objects.get(distributor=distributor, warehouse_filename=filename)
        dist_inv_file.warehouse = warehouse
        dist_inv_file.update_date = datetime.strptime(timestamp, "%m/%d/%Y %I:%M:%S %p")
        dist_inv_file.save()
        print(dist_inv_file)

        dataframe = pandas.read_excel(file, header=2)

        records = dataframe.to_dict(orient='records')
        for row in records:
            print(row)

            item, created = DistItem.objects.get_or_create(distributor=distributor,
                                                           dist_number=row.get('ItemID'),
                                                           msrp=row.get('MSRP'),
                                                           dist_name=row.get('ShortDesc'),
                                                           dist_barcode=row.get('UPC'),
                                                           )
            if row.get('Product Type') == 'NPI':
                item.dist_price = row.get('MSRP') * (1 - npi)
            item.save()
            dist_inv_file.set_availability(item, warehouse=warehouse, y_or_n=row.get('MIDDLETON'), key="YES")


def download_images(upc):
    pass  # For now do nothing


def get_name_and_msrp(upc):
    info = query_for_info(upc)
    if len(info) == 0:
        return None, None
    return info['Name'], info["MSRP"]


def query_for_info(upc, get_full=False, debug=False):
    if upc is None or "":
        return {}
    try:
        result = requests.get(
            f"https://www.acdd.com/search-advanced/results?upc={upc}")
        soup = BeautifulSoup(result.text, features="html5lib")
        script_elements = soup.find_all("script")
        # Assume only the first result matters since we are searching by UPC.
        page_data = ""
        prefix = 'self.__next_f.push([1,"'
        for script in script_elements:
            if not script.string:
                continue
            if prefix not in script.string:
                continue
            page_data += script.string[len(prefix):-len("\\n\")]")]

        readable_data = bytes(page_data, "utf-8").decode("unicode_escape")
        last_line = readable_data.splitlines()[-1]
        five_data = "[" + last_line.split("5:[")[1]
        page_json_data = json.loads(five_data)
        results = []
        search_key(page_json_data, "products", results)
        item_details = results[0][0]
        if debug:
            print(json.dumps(item_details, sort_keys=True, indent=4))

        msrp = None
        msrp_object = item_details["prices"].get("retailPrice")
        if msrp_object:
            msrp = decimal.Decimal(msrp_object["value"]).quantize(Decimal('.01'), rounding=ROUND_DOWN)
        # Don't trust any of the other prices to be the price.

        for field in item_details["customFields"]:
            item_details[field["name"]] = field["value"]

        default_image = item_details["defaultImage"]
        image_url = None
        if default_image:
            image_url = default_image["url"]

        return {
            "Name": fix_text(item_details["name"]),
            "MSRP": msrp,
            "Barcode": upc,
            "SKU": item_details["sku"],
            "Description": fix_text(item_details["description"]),
            "Picture Source": image_url,
            "Release Date": item_details.get("release_date"),
            "Publisher": item_details["manufacturer_code"],  # TODO: translate into a category
        }
    except Exception as e:
        print(f"error for {upc}: {e}")
        if debug:
            traceback.print_exc()

    return {}


def fix_text(text):  # Fix bad encoding and invalid HTML
    fixed_text = text.encode('latin-1').decode('utf-8')
    if "<" in fixed_text:
        return str(BeautifulSoup(fixed_text, "html5lib"))
    return fixed_text


def get_from_table(soup, row_heading):
    value = None
    release_date_elements = soup.find_all('td', class_="col data", attrs={"data-th": row_heading})
    if release_date_elements:
        value = release_date_elements[0].get_text()
    return value


def search_key(data, target_key, results=None):
    if results is None:
        results = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key:
                results.append(value)
            search_key(value, target_key, results)  # Recursive call

    elif isinstance(data, list):
        for item in data:
            search_key(item, target_key, results)  # Recursive call

    return results
