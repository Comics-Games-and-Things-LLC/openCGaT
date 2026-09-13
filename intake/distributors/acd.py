import decimal
import json
import re
import traceback
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

import pandas
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from djmoney.money import Money

dist_name = "ACD"
npi = .47

INVENTORY_URL = "https://store-vz3etek0gv.mybigcommerce.com/content/inventory/middleton-inventory.html"
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'
}


def update_inventory(auth=None):
    from intake.models import (
        Distributor,
        DistributorWarehouse,
        DistItem,
        DistributorInventoryFile,
        DistributorInventoryLine,
    )

    print("Starting ACD inventory update...")
    if auth:
        distributor = auth.distributor
    else:
        distributor, _ = Distributor.objects.get_or_create(dist_name=dist_name)

    warehouse, _ = DistributorWarehouse.objects.get_or_create(
        distributor=distributor,
        warehouse_name="Middleton",
        defaults={'warehouse_filename': 'middleton-inventory.html'}
    )

    print(f"Fetching inventory from {INVENTORY_URL}...")
    response = requests.get(INVENTORY_URL, headers=DEFAULT_HEADERS, timeout=60)
    response.raise_for_status()

    print(f"Downloaded inventory data ({len(response.content)} bytes). Parsing HTML table...")
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table")
    if not table:
        raise ValueError("Could not find table in inventory HTML")

    trs = table.find_all("tr")

    update_date = None
    for tr in trs[:3]:
        text = tr.get_text(" ", strip=True)
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M)", text)
        if m:
            try:
                parsed_dt = datetime.strptime(m.group(1), "%m/%d/%Y %I:%M:%S %p")
                if timezone.is_naive(parsed_dt):
                    update_date = timezone.make_aware(parsed_dt)
                else:
                    update_date = parsed_dt
                break
            except ValueError:
                pass

    if not update_date:
        update_date = timezone.now()

    print(f"Inventory timestamp: {update_date}")

    inventory_file = DistributorInventoryFile.objects.create(
        distributor=distributor,
        warehouse=warehouse,
        processed=True,
        update_date=update_date,
    )

    header_idx = None
    for i, tr in enumerate(trs[:10]):
        cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if "ItemID" in cols and "ShortDesc" in cols:
            header_idx = i
            break

    data_rows = trs[header_idx + 1:] if header_idx is not None else trs[3:]
    print(f"Processing {len(data_rows)} rows for ACD...")

    for tr in data_rows:
        cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cols or not any(cols):
            continue

        item_id = cols[0] if len(cols) > 0 else ""
        if not item_id:
            continue

        description = cols[1] if len(cols) > 1 else ""
        msrp_str = cols[2] if len(cols) > 2 else ""
        product_type = cols[3] if len(cols) > 3 else ""
        status = cols[4] if len(cols) > 4 else ""
        street_date = cols[5] if len(cols) > 5 else ""
        upc = cols[6] if len(cols) > 6 else ""
        middleton = cols[7] if len(cols) > 7 else ""

        msrp = None
        if msrp_str:
            msrp_val = re.sub(r'[^\d.]', '', msrp_str)
            if msrp_val:
                try:
                    msrp = Decimal(msrp_val)
                except Exception:
                    pass

        dist_price = None
        if product_type == 'NPI' and msrp is not None:
            dist_price = (msrp * Decimal(str(1 - npi))).quantize(Decimal('.01'), rounding=ROUND_DOWN)

        expected = None
        if street_date:
            try:
                clean_date = re.sub(r'\s+EST$', '', street_date.strip(), flags=re.IGNORECASE)
                parts = clean_date.split('/')
                if len(parts) == 3 and parts[1] == '00':
                    clean_date = f"{parts[0]}/01/{parts[2]}"
                if len(parts) == 3:
                    if len(parts[2]) == 4:
                        expected = datetime.strptime(clean_date, "%m/%d/%Y").date()
                    elif len(parts[2]) == 2:
                        expected = datetime.strptime(clean_date, "%m/%d/%y").date()
            except (ValueError, TypeError):
                pass

        in_stock = None
        if middleton:
            m_upper = middleton.strip().upper()
            if m_upper in ["YES", "Y", "TRUE", "IN"]:
                in_stock = True
            elif m_upper in ["NO", "N", "FALSE", "OUT"]:
                in_stock = False

        dist_item, created = DistItem.objects.get_or_create(
            distributor=distributor,
            dist_number=item_id,
            defaults={
                'dist_name': description,
                'msrp': Money(msrp, 'USD') if msrp is not None else None,
                'dist_price': Money(dist_price, 'USD') if dist_price is not None else None,
                'dist_barcode': upc if upc else None,
                'expected': expected,
                'in_stock': in_stock,
            }
        )
        if not created:
            if description:
                dist_item.dist_name = description
            if msrp is not None:
                dist_item.msrp = Money(msrp, 'USD')
            if dist_price is not None:
                dist_item.dist_price = Money(dist_price, 'USD')
            if upc:
                dist_item.dist_barcode = upc
            if expected is not None:
                dist_item.expected = expected
            if in_stock is not None:
                dist_item.in_stock = in_stock
            dist_item.save()

        dist_item.set_product_from_sku()

        if middleton:
            inventory_file.set_availability(dist_item, warehouse=warehouse, y_or_n=middleton, key="Yes")

        inventory_file.items.add(dist_item)

        DistributorInventoryLine.objects.create(
            inventory_file=inventory_file,
            dist_item=dist_item,
            msrp=Money(msrp, 'USD') if msrp is not None else None,
            dist_price=Money(dist_price, 'USD') if dist_price is not None else None,
            expected=expected,
            in_stock=in_stock,
        )

    inventory_file.line_count = inventory_file.inventory_lines.count()
    inventory_file.save()
    print(f"Finished ACD inventory update. Processed and saved {inventory_file.line_count} items into {inventory_file}.")
    return inventory_file


def import_records(dist_inv_file):
    from intake.models import Distributor, DistributorWarehouse, DistItem
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
            page_data += script.string[len(prefix):-len("\")]")]
        readable_data = bytes(page_data, "utf-8").decode("unicode_escape")
        last_line = readable_data.splitlines()[-1]
        five_data = "[" + last_line.split("5:[")[1]
        page_json_data = json.loads(five_data)
        results = []
        search_key(page_json_data, "initialProducts", results)
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
