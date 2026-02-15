import csv
import datetime

from django.core.management.base import BaseCommand
from moneyed import Money
from tqdm import tqdm

from intake.models import PurchaseOrder, POLine
from inventory_report.models import InventoryReport
from openCGaT.management_util import email_report
from partner.models import Partner
from shop.models import Product

partner = Partner.objects.get(name__icontains="Valhalla")


# This version of the report is simpler in that it only reports based on the inventory report,
# and works backwards from the end of the year instead of the start of sales history.

def get_latest_purchased_as(year, barcode):
    purchased_as_options = POLine.objects.filter(po__partner=partner, po__date__year__lte=year)
    purchased_as_options = purchased_as_options.filter(barcode=barcode, remaining_quantity__gte=1)
    if purchased_as_options.exists():
        p_as = purchased_as_options.order_by('-po__date').first()  # Latest purchased
        p_as.remaining_quantity = p_as.remaining_quantity - 1
        p_as.save()
        return p_as


def reset_po_sold(f):
    log(f, "Resetting PO line remaining quantities")
    for pol in tqdm(POLine.objects.all()):
        pol.remaining_quantity = pol.received_quantity
        pol.save()


def handle_inventory_report(year):
    report_name = f"EOY Inventory Cost for {year}"
    # YEAR PARAMETER IS NOT USED FOR INVENTORY REPORT CORRECTLY

    log_filename = f"reports/{report_name} Log.txt"
    f = open(log_filename, "w")

    report_file_list = [log_filename]

    log(f, f"End of year Inventory Cost Report run at {datetime.datetime.now()}")

    reset_po_sold(f)

    # This also spits out a CSV file, so we can add any missing costs in manually in a spreadsheet.
    eoy_inventory_cost = Money("0", 'USD')
    csv_filename = f'reports/{report_name} Lines.csv'
    report_file_list.append(csv_filename)

    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = ['Display Name', 'Barcode', 'Purchase order', 'Actual cost']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for line in tqdm(InventoryReport.objects.order_by("-id") \
                                 .first().report_lines.all().order_by('-id')):  # Load most recent inventory report
            display_name = ""
            if line.barcode is not None:
                try:
                    display_name = Product.objects.get(barcode=line.barcode).name
                except Product.DoesNotExist:
                    pass
            p_as = get_latest_purchased_as(year, line.barcode)
            row_info = {
                'Display Name': display_name,
                'Barcode': line.barcode,
            }
            if p_as:
                row_info['Purchase order'] = p_as.po
                if p_as.actual_cost:
                    eoy_inventory_cost += p_as.actual_cost
                    row_info['Actual cost'] = p_as.actual_cost
            writer.writerow(row_info)

    log(f, "Inventory from the inventory report costs {} ".format(eoy_inventory_cost))

    log(f, "End of report\n\n")

    f.close()
    email_report(report_name, report_file_list)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)

    def handle(self, *args, **options):
        year = options.pop('year')  # Last year by default
        if year is None:
            year = datetime.date.today().year - 1
        handle_inventory_report(year)


def log(f, string):
    print(string)
    f.write(string + "\n")
