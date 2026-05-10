import csv
import datetime
from csv import DictWriter
from typing import Any

from django.core.management.base import BaseCommand
from djmoney.money import Money
from tqdm import tqdm

from checkout.models import Cart, CheckoutLine
from game_info.models import Game
from intake.distributors.utility import log
from intake.models import POLine
from inventory_report.management.commands.GetCogs import get_purchased_as, mark_previous_items_as_sold, partner
from inventory_report.management.commands.GetEOYInventory import reset_po_sold, get_latest_purchased_as
from inventory_report.models import InventoryReport
from openCGaT.management_util import email_report
from shop.models import Product, Publisher, Category, Item

GAME = "Game"
PUBLISHER = "Publisher"
CATEGORY = "Category"


def get_sales_summary(thing=GAME, **options):
    '''
    New version of the sales report,
    getting the overall collected and spend compared to attempting to calculate the value on each sale.
    :param thing: Type of thing to categorize by
    :param options: Parameters, year or all.
    :return:
    '''
    verbose = True  # if we want to print errors.

    year = options.pop('year')  # Last year by default
    if year is None:
        year = datetime.date.today().year - 1
    all_time = options.pop("all")
    if all_time:
        year = None
    display_year = year
    if year is None:
        display_year = "all time"

    report_name = f"Earnings by {thing} for {display_year}"

    log_filename = f"reports/{report_name} Log.txt"
    f = open(log_filename, "w")
    lines_filename = f'reports/{report_name} Lines.csv'
    fieldnames = [thing, 'Year', 'Display Name', 'Barcode', 'Purchase order', 'Actual cost']
    lines_file = open(lines_filename, 'w', newline='')
    lines_writer = csv.DictWriter(lines_file, fieldnames=fieldnames)
    lines_writer.writeheader()

    sales_filename = f'reports/{report_name} Sales.csv'
    fieldnames = [thing, 'Date', 'Product', 'Quantity', 'Collected', 'We Spent on Shipping']
    sales_file = open(sales_filename, 'w', newline='')
    sales_writer = csv.DictWriter(sales_file, fieldnames=fieldnames)
    sales_writer.writeheader()

    summary_filename = f'reports/{report_name} Summary.csv'
    fieldnames = [thing, 'Starting Inventory', 'Spent on Inventory', 'Ending Inventory', 'Invested Inventory', 'COGS',
                  'Collected',
                  'We Spent on Shipping', 'Gross less Shipping', 'Overall Net Costs (Includes Investment)',
                  'Net from COGS (Excludes Investment)', 'Collected Locally', '% Local']
    summary_file = open(summary_filename, 'w', newline='')
    summary_writer = csv.DictWriter(summary_file, fieldnames=fieldnames)
    summary_writer.writeheader()

    report_file_list = [log_filename, lines_filename, sales_filename, summary_filename]

    reset_po_sold(f)

    cart_lines = CheckoutLine.objects.filter(partner_at_time_of_submit=partner,
                                             cart__status__in=[Cart.PAID, Cart.COMPLETED]).order_by("cart__date_paid")
    if year:
        cart_lines = cart_lines.filter(cart__date_paid__year=year)

    if thing == PUBLISHER:
        object_to_iterate_on = Publisher.objects.all().order_by('name')
    elif thing == CATEGORY:
        object_to_iterate_on = Category.objects.filter(level__lte=0).order_by('name')
    else:
        object_to_iterate_on = Game.objects.all().order_by('name')

    for thing_instance in list(object_to_iterate_on) + [None]:
        if thing_instance:
            name = thing_instance.name
        else:
            name = f"No {thing}"

        if thing == CATEGORY:
            thing_instance = thing_instance.get_descendants(include_self=True)

        log(f, f"Reporting on {name}")

        starting_inventory = Money("0", 'USD')
        ending_inventory = Money("0", 'USD')
        spent_on_inventory = Money("0", 'USD')
        spent_on_shipping = Money("0", 'USD')
        collected = Money("0", 'USD')
        collected_locally = Money("0", 'USD')

        product_barcodes = get_product_barcodes(thing, thing_instance)

        # First, get starting inventory if relevant:
        if year:
            # For sales of 2025, get the 2025 inventory report as a baseline.
            starting_inventory = get_total_from_inv_report(lines_writer, thing, product_barcodes, year)
        # Now get how much we spent on inventory for the year.
        spent_on_inventory = get_purchased_this_year_total(year, product_barcodes)

        # Also get inventory remaining for the year from the next year:
        try:
            ending_inventory = get_total_from_inv_report(lines_writer, thing, product_barcodes, year + 1)
        except Exception as e:
            print(e)  # Maybe the report doesn't exist, not too worried about it.

        # Now get the total spent on inventory:
        filtered_cart_lines = cart_lines.filter(item__product__barcode__in=product_barcodes)

        for line in filtered_cart_lines:
            collected_on_line = line.get_subtotal()
            shipping_on_line = line.get_proportional_postage_paid()
            sales_writer.writerow({
                thing: thing_instance,
                "Date": line.cart.date_paid,
                "Product": line.item.product,
                "Quantity": line.quantity,
                "Collected": collected_on_line,
                "We Spent on Shipping": shipping_on_line,
            })
            collected += collected_on_line
            if not (shipping_on_line.amount > 0):
                collected_locally += collected_on_line
            spent_on_shipping += shipping_on_line
        cogs = spent_on_inventory - (ending_inventory - starting_inventory)
        row_data = {
            thing: thing_instance,
            'Starting Inventory': starting_inventory,
            'Spent on Inventory': spent_on_inventory,
            'Ending Inventory': ending_inventory,
            'Invested Inventory': (ending_inventory - starting_inventory),
            'COGS': cogs,
            'Collected': collected,
            'We Spent on Shipping': spent_on_shipping,
            'Gross less Shipping': collected - spent_on_shipping,
            'Overall Net Costs (Includes Investment)': collected - spent_on_shipping - spent_on_inventory,
            'Net from COGS (Excludes Investment)': collected - spent_on_shipping - cogs,
            'Collected Locally': collected_locally,
        }
        if collected:
            try:
                row_data['% Local'] = (collected_locally / collected)
            except TypeError:
                print("Collected Locally: ", type(collected_locally), collected_locally)
                print("Collected        : ", type(collected), collected)
                # Checking for differences between money and djmoney
                exit()

        summary_writer.writerow(row_data)

    # Close all the files
    f.close()
    summary_file.close()
    sales_file.close()
    lines_file.close()

    email_report(report_name, report_file_list)


def get_purchased_this_year_total(year: int | None, product_barcodes):
    total = Money("0", 'USD')
    for line in tqdm(POLine.objects.filter(po__date__year=year, barcode__in=product_barcodes),
                     desc="Calculating total purchases"):
        subtotal = line.actual_cost_subtotal
        if subtotal is None:
            continue
        total += subtotal
    return total


def get_total_from_inv_report(lines_writer: DictWriter, thing: str, product_barcodes,
                              year: int | None):
    inventory_cost = Money("0", 'USD')
    previous_inventory_report = InventoryReport.objects.get(date__year=year)
    for line in tqdm(previous_inventory_report.report_lines.filter(barcode__in=product_barcodes).order_by('-id')):
        display_name = ""
        if line.barcode is not None:
            try:
                display_name = Product.objects.get(barcode=line.barcode).name
            except Product.DoesNotExist:
                pass
        p_as = get_latest_purchased_as(year, line.barcode)
        row_info = {
            thing: display_name,
            'Year': year,
            'Display Name': display_name,
            'Barcode': line.barcode,
        }
        if p_as:
            row_info['Purchase order'] = p_as.po
            if p_as.actual_cost:
                inventory_cost += p_as.actual_cost
                row_info['Actual cost'] = p_as.actual_cost
        lines_writer.writerow(row_info)
    return inventory_cost


def get_product_barcodes(thing: str, thing_instance) -> Any:
    if thing == PUBLISHER:
        products = Product.objects.filter(publisher=thing_instance)
    elif thing == CATEGORY:
        products = Product.objects.filter(categories__in=thing_instance)
    else:
        products = Product.objects.filter(games=thing_instance)

    product_barcodes = products.values_list("barcode", flat=True)
    return product_barcodes


def get_sales_by_thing(thing=GAME, **options):
    verbose = True  # if we want to print errors.

    year = options.pop('year')  # Last year by default
    if year is None:
        year = datetime.date.today().year - 1
    all_time = options.pop("all")
    if all_time:
        year = None
    display_year = year
    if year is None:
        display_year = "all time"

    report_name = f"Earnings by {thing} for {display_year}"

    f = open(f"reports/{report_name}.txt", "a", encoding="UTF-8")

    f2 = open(f"reports/{report_name} entries.csv", "w", encoding="UTF-8")
    entries_writer = csv.DictWriter(f2, [f"{thing}", "Product", "Quantity", "Cart",
                                         "Collected", "Shipping", "Spent",
                                         "Total Costs", "Net", "Margin"])
    entries_writer.writeheader()

    f3 = open(f"reports/{report_name}.csv", "w", encoding="UTF-8")
    summary_writer = csv.DictWriter(f3, [f"{thing}", "Spent on Sold", "Shipping on Sold", "Costs on Sold",
                                         "Collected", "Collected for events", "Collected Locally", "Spent this year"])
    summary_writer.writeheader()

    log(f, f"{report_name}:")

    cart_lines = CheckoutLine.objects.filter(partner_at_time_of_submit=partner,
                                             cart__status__in=[Cart.PAID, Cart.COMPLETED]).order_by("cart__date_paid")
    if year:
        cart_lines = cart_lines.filter(cart__date_paid__year=year)

    # Cleanup previous purchased as data first
    mark_previous_items_as_sold(f, year, verbose=verbose)

    if thing == PUBLISHER:
        object_to_iterate_on = Publisher.objects.all().order_by('name')
    elif thing == CATEGORY:
        object_to_iterate_on = Category.objects.filter(level__lte=0).order_by('name')
    else:
        object_to_iterate_on = Game.objects.all().order_by('name')

    for thing_instance in list(object_to_iterate_on) + [None]:
        if thing_instance:
            name = thing_instance.name
        else:
            name = f"No {thing}"
        if thing == CATEGORY:
            thing_instance = thing_instance.get_descendants(include_self=True)

        spent_on_sold_for_game = Money("0", 'USD')
        shipping_on_game = Money("0", 'USD')
        costs_on_sold_for_game = Money("0", 'USD')
        collected_on_game = Money("0", 'USD')
        collected_on_game_events = Money("0", 'USD')
        collected_locally = Money("0", 'USD')

        if verbose:
            log(f, "Errors for {}:".format(name))

        if thing == PUBLISHER:
            filtered_cart_lines = cart_lines.filter(item__product__publisher=thing_instance)
        elif thing == CATEGORY:
            filtered_cart_lines = cart_lines.filter(item__product__categories__in=thing_instance)
        else:
            filtered_cart_lines = cart_lines.filter(item__product__games=thing_instance)

        for line in filtered_cart_lines:
            try:
                if line.item and line.item.product and line.item.product.barcode:
                    spent_on_line = get_purchased_as(line.item.product.barcode, line.quantity, f, line,
                                                     verbose=verbose)
                    collected_on_line = line.get_subtotal()
                    shipping_on_line = line.get_proportional_postage_paid()
                    costs_on_line = Money(spent_on_line.amount + shipping_on_line.amount, 'USD')
                    rowdata = {
                        f"{thing}": thing_instance,
                        "Product": line.item.product,
                        "Quantity": line.quantity,
                        "Spent": spent_on_line.amount,
                        "Collected": collected_on_line.amount,
                        "Shipping": shipping_on_line.amount,
                        "Total Costs": costs_on_line.amount,
                        "Net": collected_on_line.amount - costs_on_line.amount,

                    }
                    if collected_on_line.amount > 0 and costs_on_line.amount > 0:
                        rowdata.update({"Margin": 1 - (costs_on_line.amount / collected_on_line.amount),
                                        })
                    entries_writer.writerow(rowdata)
                    spent_on_sold_for_game += spent_on_line
                    costs_on_sold_for_game += costs_on_line
                    shipping_on_game += shipping_on_line
                    if line.item.product.categories.filter(name="Events").exists():
                        collected_on_game_events += collected_on_line
                    else:
                        collected_on_game += collected_on_line
                        if (line.cart.final_ship is None) or line.cart.final_ship.amount == 0:
                            collected_locally += collected_on_line
                else:
                    log(f, "{} no longer has an item".format(line))

            except Item.DoesNotExist as e:
                log(f, f"Error during processing {thing_instance}:")
                log(f, str(e))
                log(f, f"Could not get line.item for {line}")

        # Now get the amount we spent on inventory for said game.
        spent_on_game = Money("0", 'USD')

        if thing == PUBLISHER:
            product_barcodes = Product.objects.filter(publisher=thing_instance).values_list('barcode', flat=True)
        elif thing == CATEGORY:
            product_barcodes = Product.objects.filter(categories__in=thing_instance).values_list('barcode', flat=True)
        else:
            product_barcodes = Product.objects.filter(games=thing_instance).values_list('barcode', flat=True)

        po_lines = POLine.objects.filter(po__partner=partner)
        if year:
            po_lines = po_lines.filter(po__date__year=year)
        for line in po_lines.filter(barcode__in=product_barcodes):
            try:
                spent_on_game += Money(line.actual_cost.amount * line.expected_quantity, 'USD')
            except AttributeError:
                if verbose:
                    log(f, "Could not get cost for {} from {}".format(line.name, line.po))

        if (collected_on_game.amount == spent_on_game.amount
                == collected_on_game_events.amount == spent_on_sold_for_game.amount == 0):
            continue  # Don't bother printing the empty games

        log(f, "{}:".format(name))

        log(f, "\t{} was collected from customers".format(collected_on_game))
        log(f, "\t{} was spent on that inventory, for a net of {}"
            .format(spent_on_sold_for_game,
                    collected_on_game - spent_on_sold_for_game))
        total_net = collected_on_game - spent_on_sold_for_game - shipping_on_game
        log(f, "\t{} was spent on shipping orders, for a total net of {}"
            .format(shipping_on_game, total_net))

        extra_spent = spent_on_game - spent_on_sold_for_game

        if extra_spent.amount > 0:
            more_or_less = "more"
        else:
            more_or_less = "less"

        net_counting_inventory = total_net - extra_spent
        if net_counting_inventory.amount < 0:
            affect = "invested"
        else:
            affect = "made"

        log(f, f"\t{spent_on_game} was spent on that {thing}'s inventory{' this year' if year else ''}, "
               f"\t\t{abs(extra_spent)} {more_or_less} than on inventory sold, "
               f"\t\tso we {affect} {abs(net_counting_inventory)}")

        if collected_on_game_events.amount > 0:
            log(f, f"\t{collected_on_game_events} was collected on events,"
                   " which could make up for some of that?")

        if collected_locally.amount > 0:
            log(f, f"\t{collected_locally} was collected on pickup orders," +
                " or {:.0f}%".format(collected_locally.amount * 100 / collected_on_game.amount))

        summary_writer.writerow(
            {f"{thing}": name,
             "Spent on Sold": spent_on_sold_for_game.amount,
             "Shipping on Sold": shipping_on_game.amount,
             "Costs on Sold": costs_on_sold_for_game.amount,
             "Collected": collected_on_game.amount,
             "Collected for events": collected_on_game_events.amount,
             "Collected Locally": collected_locally.amount,
             "Spent this year": spent_on_game}
        )

    log(f, "End of report\n\n")
    f.close()
    f2.close()
    f3.close()
    print(f"Results and errors in in '{f.name}'")
    print(f"CSV results in '{f3.name}'")
    print(f"Per-line results in '{f2.name}'")
    email_report(report_name, [f.name, f2.name, f3.name])


class Command(BaseCommand):
    # Known bug: If a product is under multiple games, it will mark it as sold by the first game, and then not be
    # available to check for the second game. One way of solving this would be to reset the "sold" count between games.

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)
        parser.add_argument("--all", action='store_true')

    def handle(self, *args, **options):
        get_sales_summary(GAME, **options)
