import csv
import datetime

from django.core.management.base import BaseCommand
from moneyed import Money
from tqdm import tqdm

from checkout.models import Cart
from intake.models import PurchaseOrder, POLine
from inventory_report.models import InventoryReport
from openCGaT.management_util import email_report
from partner.models import Partner
from shop.models import Product, InventoryItem

partner = Partner.objects.get(name__icontains="Valhalla")


def get_purchased_as(barcode, quantity, logfile, cart_line=None, verbose=True, year=None) -> Money:
    cost = Money(0, "USD")
    display_name = str(cart_line)
    if cart_line is None:
        display_name = barcode
        if barcode is not None:
            try:
                display_name = Product.objects.get(barcode=barcode).name
            except Product.DoesNotExist:
                pass

    if quantity is None:
        quantity = cart_line.quantity
    purchased_as_options = POLine.objects.filter(po__partner=partner, barcode=barcode, remaining_quantity__gte=1)
    if year:
        purchased_as_options = purchased_as_options.filter(po__date__year__lte=year)
    if purchased_as_options.exists():
        p_as = purchased_as_options.order_by('po__date').first()
        new_quantity = p_as.remaining_quantity - quantity

        fulfilled_quantity = quantity
        if new_quantity < 0:
            fulfilled_quantity = quantity - p_as.remaining_quantity
            p_as.remaining_quantity = 0
            p_as.save()
            cost += get_purchased_as(barcode, abs(new_quantity), logfile, cart_line, verbose, year)
        else:
            p_as.remaining_quantity = new_quantity

        if p_as.actual_cost:
            cost += Money(p_as.actual_cost.amount * fulfilled_quantity, 'USD')
        else:
            if verbose:
                log(logfile, "{} does not have an actual cost in poline {}".format(display_name, p_as))
        p_as.save()
    else:
        if verbose:
            log(logfile,
                "{} did not have any quantity to allocate. It could be a pre or backorder as of the end of the year".format(
                    display_name))
        ever_purchased = POLine.objects.filter(po__partner=partner, barcode=barcode)
        if year:
            ever_purchased = ever_purchased.filter(po__date__year__lte=year)
        if not ever_purchased.exists():
            log(logfile,
                "{} ({}) has never never been on a purchase order in or before {}".format(display_name, barcode, year))
    return cost


def get_purchased_as_line(year, barcode, display_name, logfile, verbose=True):
    purchased_as_options = POLine.objects.filter(po__partner=partner, po__date__year__lte=year)
    purchased_as_options = purchased_as_options.filter(barcode=barcode, remaining_quantity__gte=1)
    if purchased_as_options.exists():
        p_as = purchased_as_options.order_by('po__date').first()
        new_quantity = p_as.remaining_quantity - 1
        p_as.remaining_quantity = new_quantity
        p_as.save()
        return p_as
    else:
        if verbose:
            log(logfile,
                "{} did not have any quantity to allocate. It could be a pre or backorder as of the end of the year".format(
                    display_name))
        ever_purchased = POLine.objects.filter(po__partner=partner, po__date__year__lte=year).filter(barcode=barcode)
        if not ever_purchased.exists():
            log(logfile,
                "{} ({}) has never never been on a purchase order in or before {}".format(display_name, barcode, year))


def mark_previous_items_as_sold(f, year=None, verbose=True):
    log(f, "Resetting PO line remaining quantities")
    for pol in tqdm(POLine.objects.all()):
        pol.remaining_quantity = pol.received_quantity
        pol.save()

    if year == None:
        return

    # Get all carts for the years before to ensure those items are removed from inventory first.
    cost_of_goods_sold = Money("0", 'USD')
    for cart in tqdm(Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED],
                                           date_submitted__year__lt=year).order_by("date_submitted")):
        for line in cart.lines.filter(partner_at_time_of_submit=partner, item__isnull=False):
            try:
                item = InventoryItem.objects.get(id=line.item_id)
                if item.product:
                    cost_of_goods_sold += get_purchased_as(item.product.barcode, line.quantity,
                                                           f, line, verbose=verbose)
                else:
                    if verbose:
                        log(f, "{} no longer has a product".format(line))
            except InventoryItem.DoesNotExist:
                log(f, f"{line} contains an item ID that does not exist: {line.item_id}")

    if verbose:
        log(f, "The total cost of goods sold before {} is {}".format(year, cost_of_goods_sold))


def handle_get_cogs(year, have_inv_report=False):
    report_name = f"COGS {year}"
    if have_inv_report:
        report_name = f"Estimated COGS {datetime.date.today()}"

    log_filename = f"reports/{report_name} log.txt"
    f = open(log_filename, "w")
    missing_costs_filename = f"reports/{report_name} Missing Costs.txt"
    f2 = open(missing_costs_filename, "w")

    report_file_list = [log_filename, missing_costs_filename]

    log(f, "End of year Cost of Goods Sold Report")

    total_inventory_purchased = Money("0", 'USD')
    for po in PurchaseOrder.objects.filter(date__year=year, partner=partner):
        for line in po.lines.all():
            if line.actual_cost:
                total_inventory_purchased += (line.actual_cost * line.received_quantity)
    log(f, "{} of inventory was purchased in {}".format(total_inventory_purchased, year))

    # Get cogs for the year in question
    cost_of_goods_sold = Money("0", 'USD')

    mark_previous_items_as_sold(f, year)

    for cart in tqdm(Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED]) \
                             .filter(date_submitted__year=year) \
                             .order_by("date_submitted")):
        for line in cart.lines.filter(partner_at_time_of_submit=partner):
            try:
                cost_of_goods_sold += get_purchased_as(line.item.product.barcode, line.quantity, f2, line)
            except Exception:
                log(f, "{} no longer has an item".format(line))
    log(f, "The total cost of goods sold for the year {} is {}"
        .format(year, cost_of_goods_sold))

    mark_previous_items_as_sold(f, year, verbose=False)

    # Now that we've marked all the items from this year as sold, find the remaining items according to purchase orders.
    # That'll be our remaining inventory for the year.
    unsold_inventory_po_cost = Money("0", 'USD')
    for po in tqdm(PurchaseOrder.objects.filter(date__year__lte=year, partner=partner)):
        for line in po.lines.all():
            if line.actual_cost:
                unsold_inventory_po_cost += (line.actual_cost * line.remaining_quantity)
            else:
                log(f, "PO Line {} is missing actual cost".format(line))

    log(f, "Unsold inventory up to the end of {} according to purchase orders: {}".format(year,
                                                                                          unsold_inventory_po_cost))

    # Also get the same number from the inventory report if we have it, might be slightly different
    # This also spits out a CSV file, so we can add any missing costs in manually in a spreadsheet.
    unsold_inventory_cost = Money("0", 'USD')
    if have_inv_report:
        csv_filename = f'reports/{report_name} Inventory.csv'
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
                p_as = get_purchased_as_line(year, line.barcode, display_name, f2)
                row_info = {
                    'Display Name': display_name,
                    'Barcode': line.barcode,
                }
                if p_as:
                    row_info['Purchase order'] = p_as.po
                    if p_as.actual_cost:
                        unsold_inventory_cost += p_as.actual_cost
                        row_info['Actual cost'] = p_as.actual_cost
                writer.writerow(row_info)

        log(f, "Inventory from the inventory report costs {} ".format(unsold_inventory_cost))
    else:
        for item in InventoryItem.objects.filter(current_inventory__gt=0):
            try:
                estimated_cost = POLine.objects.filter(po__partner=partner, barcode=item.product.barcode).order_by(
                    '-po__date').first().cost_per_item
                unsold_inventory_cost += estimated_cost * item.current_inventory

            except Exception:
                log(f, f"Could not get cost for {item.current_inventory} x {item.product.name}")

        log(f, f"Remaining Inventory cost estimate {unsold_inventory_cost}")

    log(f, "Cost of inventory purchased minus cost of goods sold (Theoretically equal to above?) : {}".format(
        total_inventory_purchased - cost_of_goods_sold))

    log(f, "Cost of inventory purchased minus remaining inventory: (COGS) : {}".format(
        total_inventory_purchased - unsold_inventory_cost))

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
        handle_get_cogs(year, True)


def log(f, string):
    print(string)
    f.write(string + "\n")
