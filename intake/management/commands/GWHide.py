import os
import pandas
from django.core.management.base import BaseCommand
from intake.distributors.games_workshop import hide_products
from openCGaT.management_util import email_report
from shop.models import Publisher, Item


class Command(BaseCommand):
    help = "Hides all Games Workshop products not in the trade range"

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Specific trade range file to use')

    def handle(self, *args, **options):
        trade_range_path = options.get('file')
        if not trade_range_path:
            trade_range_name = None
            inventories_path = './intake/inventories/'
            if os.path.exists(inventories_path):
                for filename in os.listdir(inventories_path):
                    if "Trade Range" in filename or "USA PRICE RISE" in filename or "US Price Adjustment" in filename:
                        trade_range_name = filename
            if trade_range_name is None:
                self.stdout.write(self.style.ERROR("Please have a file with 'Trade Range' or 'USA Price Rise' in the inventories folder"))
                return
            trade_range_path = os.path.join(inventories_path, trade_range_name)

        if not os.path.exists(trade_range_path):
            self.stdout.write(self.style.ERROR(f"File not found: {trade_range_path}"))
            return

        file = pandas.ExcelFile(trade_range_path)
        sheet_name = 'USA' if 'USA' in file.sheet_names else 0
        if "US Price Adjustment" in trade_range_path:
            dataframe = pandas.read_excel(file, header=3, sheet_name='USD Pricelist',
                                          converters={'Product': str, 'Barcode': str, 'Product Code': str})
        else:
            dataframe = pandas.read_excel(file, header=0, sheet_name=sheet_name,
                                          converters={'Product': str, 'Barcode': str})

        records = dataframe.to_dict(orient='records')
        checked_short_codes = []
        for row in records:
            short_code = row.get('Short Code', row.get("SS Code", row.get("Short Sales Code", row.get("Short"))))
            if pandas.isna(short_code) or str(short_code).lower() == 'nan':
                short_code = None
            else:
                short_code = str(short_code).strip()

            if short_code:
                checked_short_codes.append(short_code)

        publisher, _ = Publisher.objects.get_or_create(name="Games Workshop")
        hidden_products_log = hide_products(checked_short_codes, publisher)
        hidden_products_log.flush()
        reset_prices(publisher)
        email_report("GW Hidden Products", [hidden_products_log.name])
        self.stdout.write(self.style.SUCCESS(f"Finished hiding GW products. Checked {len(checked_short_codes)} short codes."))

def reset_prices(publisher):
    for item in Item.objects.filter(product__publisher=publisher):
        if item.default_price and item.price != item.default_price:
            item.price = item.default_price
            item.save()