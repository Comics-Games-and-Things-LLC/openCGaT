import os

import pandas
from django.core.management.base import BaseCommand

from shop.models import InventoryItem


class Command(BaseCommand):

    def handle(self, *args, **options):
        inventories_path = './intake/inventories/'
        file = pandas.ExcelFile(os.path.join(inventories_path, "BSF (new).xlsx"))
        dataframe = pandas.read_excel(file, header=0)
        print(dataframe)
        for index, row in dataframe.iterrows():
            row_as_dict = row.to_dict()
            short_code = row_as_dict.get('Short Code')
            if short_code is None:
                continue
            qty = 0
            for item in InventoryItem.objects.filter(product__publisher_short_sku=short_code):
                qty += item.current_inventory
            print(qty)
            dataframe.at[index, "On Hand Qty"] = qty

        dataframe.to_excel(file)


def log(f, string):
    print(string)
    f.write(string + "\n")
