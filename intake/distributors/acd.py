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


def query_for_info(upc, get_full=False):
    try:
        result = requests.get(
            f"https://www.acdd.com/catalogsearch/advanced/result/?name=&sku=&description=&price%5Bfrom%5D=&price%5Bto%5D=&acd_upc={upc}&acd_preorder=&acd_instock=")
        soup = BeautifulSoup(result.text, features="html5lib")
        card_elements = soup.find_all("li", class_="item product product-item")
        # Assume only one result since we are searching by UPC.
        link_element = card_elements[0].find_next("a", class_="product-item-link")
        page_link = link_element['href']
        name = link_element.get_text().strip()
        acd_msrp = card_elements[0].find_next(
            "div",
            class_="msrp-value"
        ).find_next(
            "span",
            class_="price"
        ).get_text().replace("$", "")
        if not get_full:
            return {
                "Name": name,
                "MSRP": acd_msrp,
            }
        print("Querying for more information")
        print(page_link)
        result = requests.get(page_link)
        soup = BeautifulSoup(result.text, features="html5lib")
        description_elements = soup.find_all("div", class_="product attribute description")
        description = None
        if description_elements:
            description = description_elements[0].get_text()
        picture_elements = soup.find_all("img",
                                         class_="gallery-placeholder__image")

        if upc != get_from_table(soup, "UPC"):
            raise Exception("We found the wrong product!")

        picture_src = None
        if picture_elements:
            picture_src = picture_elements[0]['src']

        release_date = get_from_table(soup, "Release Date")
        if release_date:  # <Month 3 letter> Day, Year
            release_date = datetime.strptime(release_date, '%b %d, %Y').date()

        return {
            "Name": name,
            "MSRP": acd_msrp,
            "Publisher": get_from_table(soup, "Manufacturer"),
            "Category": get_from_table(soup, "Category"),
            "Barcode": upc,
            "SKU": get_from_table(soup, "SKU"),
            "Description": description,
            "Picture Source": picture_src,
            "Release Date": release_date
        }
    except Exception as e:
        print(e)
    return {}


def get_from_table(soup, row_heading):
    value = None
    release_date_elements = soup.find_all('td', class_="col data", attrs={"data-th": row_heading})
    if release_date_elements:
        value = release_date_elements[0].get_text()
    return value
