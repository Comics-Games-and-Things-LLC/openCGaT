import csv
import datetime

from django.core.management import BaseCommand
from djmoney.money import Money
from tqdm import tqdm

from inventory_report.management.commands.GetCogs import mark_previous_items_as_sold, get_purchased_as_line, log
from openCGaT.management_util import email_report
from shop.models import InventoryItem


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=datetime.date.today().year)

    def handle(self, *args, **options):
        year = options.pop('year')
        if year is None:
            print("No year specified")  # Should not happen as we default this year.
            return
        report_name = f"Approximate Inventory Value as of {datetime.date.today().isoformat()}"

        log_filename = f'reports/{report_name} log.txt'
        csv_filename = f'reports/{report_name} Inventory.csv'

        logfile = open(log_filename, "w")

        log(logfile, f"Marking all sold items as already sold so we can exclude them when getting costs")
        # This should include everything sold in that year.
        mark_previous_items_as_sold(logfile, year + 1, verbose=False)

        unsold_inventory_cost = Money("0", 'USD')

        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = ['Display Name', 'Barcode', 'Purchase order', 'Actual cost']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for item in tqdm(
                    InventoryItem.objects.filter(current_inventory__gt=0),
                    desc="Processing in stock items"
            ):  # For every inventory item in stock
                for i in range(0, item.current_inventory):  # Iterate once for each item in stock
                    row_info = {
                        'Display Name': item.product.name,
                        'Barcode': item.product.barcode,
                    }
                    p_as = get_purchased_as_line(year, item.product.barcode, item.product.name, logfile)
                    if p_as:
                        row_info['Purchase order'] = p_as.po
                        if p_as.actual_cost:
                            unsold_inventory_cost += p_as.actual_cost
                            row_info['Actual cost'] = p_as.actual_cost
                    writer.writerow(row_info)

        log(logfile, f"Costs of every in stock item we have: {unsold_inventory_cost}")
        logfile.close()
        email_report(f"{report_name} : {unsold_inventory_cost} ", [log_filename, csv_filename])
