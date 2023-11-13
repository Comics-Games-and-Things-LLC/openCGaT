import csv
import datetime
import os

import pytz
from django.core.management.base import BaseCommand
from django.db.models import Max

from shop.models import Product

utc = pytz.UTC


def get_item_info(barcode):
    # for each item we want
    # number currently in stock
    # how much we paid for it
    # maybe number sold in the past 6 months.
    try:
        product = Product.objects.get(barcode=barcode)
    except Product.DoesNotExist:
        return
    if product is None:
        return
    purchases = product.get_sold_info(product.partner)["po_lines"]
    cost = "$" + str(round(purchases.aggregate(Max("cost_per_item"))["cost_per_item__max"], 2))
    name = product.name
    item = product.item_set.first()
    inventory = item.get_inventory()
    print(name, inventory, cost)
    return {"Name": name,
            "Current Inventory": inventory,
            "Cost": cost,
            "MSRP": product.msrp}


def check_item_sales(product: Product):
    info = product.get_sold_info(product.partner)

    sales = info["sales"]
    if len(sales) == 0:
        return
    if sales.first() is None or sales.first().cart.date_submitted is None:
        return
    if sales.first().cart.date_submitted > utc.localize(datetime.datetime.now() - datetime.timedelta(days=180)):
        return
    # hasn't been sold in 6 months.

    item = product.item_set.first()
    if item is None:
        return
    inventory = item.get_inventory()

    if inventory <= 2:
        return

    purchases = info["po_lines"]
    try:
        cost = "$" + str(round(purchases.aggregate(Max("cost_per_item"))["cost_per_item__max"], 2))
    except Exception as e:
        return  # Cost for this item is not set
    name = product.name
    inventory = item.get_inventory()
    print(name, inventory, cost)
    return {"Name": name,
            "Current Inventory": inventory,
            "Cost": cost,
            "MSRP": product.msrp}


class Command(BaseCommand):
    def handle(self, *args, **options):
        year = datetime.date.today().year
        out_lines = []
        with open("reports/black_friday_out{}.csv".format(year), "w") as out_file:
            # Black_friday_in is a list of barcodes
            if os.path.exists("reports/black_friday_in.csv"):
                with open("reports/black_friday_in.csv", "r") as fp:
                    for line in csv.reader(fp):
                        if not line:
                            continue
                        barcode = line[0]
                        try:
                            out_lines.append(get_item_info(barcode))
                        except Exception:
                            pass
                    print(out_lines)

            else:
                # If we didn't have any lines to go off of, lets find some items:
                for product in Product.objects.all():
                    result = check_item_sales(product)
                    if result is not None:
                        out_lines.append(result)

            # Write info to file
            writer = csv.DictWriter(out_file, list(out_lines[0].keys()))
            writer.writeheader()
            for line in out_lines:
                if line:
                    writer.writerow(line)


def log(f, string):
    print(string)
    f.write(string + "\n")
