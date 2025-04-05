import csv
import datetime

from django.core.management.base import BaseCommand
from moneyed import Money

from checkout.models import Cart, CheckoutLine
from game_info.models import Game
from intake.distributors.utility import log
from intake.models import POLine
from inventory_report.management.commands.GetCogs import get_purchased_as, mark_previous_items_as_sold, partner
from openCGaT.management_util import email_report
from shop.models import Product, Publisher, Category, Item

GAME = "Game"
PUBLISHER = "Publisher"
CATEGORY = "Category"


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

    for thing_instance in object_to_iterate_on:
        name = thing_instance.name
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
                        if line.cart.final_ship.amount == 0:
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
        get_sales_by_thing(GAME, **options)
