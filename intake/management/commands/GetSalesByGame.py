import csv

from django.core.management.base import BaseCommand
from moneyed import Money

from checkout.models import Cart, CheckoutLine
from game_info.models import Game
from intake.distributors.utility import log
from intake.models import POLine
from inventory_report.management.commands.GetCogs import get_purchased_as, mark_previous_items_as_sold, year, partner
from shop.models import Product


class Command(BaseCommand):
    # Known bug: If a product is under multiple games, it will mark it as sold by the first game, and then not be
    # available to check for the second game. One way of solving this would be to reset the "sold" count between games.

    # Update year in GetCogs
    def handle(self, *args, **options):

        verbose = True  # if we want to print errors.

        f = open("reports/earnings by game.txt", "a")
        f2 = open("reports/earnings by game entries.csv", "w")
        detailed_writer = csv.DictWriter(f2, ["Game", "Product", "Quantity", "Cart",
                                              "Collected", "Shipping", "Spent",
                                              "Total Costs", "Net", "Margin"])
        detailed_writer.writeheader()

        log(f, "End of year Earnings by Game report")
        cart_lines = CheckoutLine.objects.filter(partner_at_time_of_submit=partner,
                                                 cart__status__in=[Cart.PAID, Cart.COMPLETED],
                                                 cart__date_paid__year=year).order_by("cart__date_paid")

        # Cleanup previous purchased as data first
        mark_previous_items_as_sold(f, year, verbose=verbose)

        for game in Game.objects.all().order_by('name'):
            spent_on_sold_for_game = Money("0", 'USD')
            shipping_on_game = Money("0", 'USD')
            costs_on_sold_for_game = Money("0", 'USD')
            collected_on_game = Money("0", 'USD')
            collected_on_game_events = Money("0", 'USD')

            if verbose:
                log(f, "Errors for {}:".format(game.name))

            for line in cart_lines.filter(item__product__games=game):
                if line.item and line.item.product and line.item.product.barcode:
                    po_out = []
                    spent_on_line = get_purchased_as(line.item.product.barcode, line.quantity, f, line,
                                                     verbose=verbose)
                    collected_on_line = line.get_subtotal()
                    shipping_on_line = line.get_proportional_postage_paid()
                    costs_on_line = Money(spent_on_line.amount + shipping_on_line.amount, 'USD')
                    rowdata = {
                        "Game": game,
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
                    detailed_writer.writerow(rowdata)
                    spent_on_sold_for_game += spent_on_line
                    costs_on_sold_for_game += costs_on_line
                    shipping_on_game += shipping_on_line
                    if line.item.product.categories.filter(name="Events").exists():
                        collected_on_game_events += collected_on_line
                    else:
                        collected_on_game += collected_on_line

                else:
                    log(f, "{} no longer has an item".format(line))

            # Now get the amount we spent on inventory for said game.
            spent_on_game = Money("0", 'USD')

            product_barcodes = Product.objects.filter(games=game).values_list('barcode', flat=True)
            po_lines = POLine.objects.filter(po__partner=partner, po__date__year=year)
            for line in po_lines.filter(barcode__in=product_barcodes):
                try:
                    spent_on_game += Money(line.actual_cost.amount * line.expected_quantity, 'USD')
                except AttributeError:
                    if verbose:
                        log(f, "Could not get cost for {} from {}".format(line.name, line.po))

            if (collected_on_game.amount == spent_on_game.amount
                    == collected_on_game_events.amount == spent_on_sold_for_game.amount == 0):
                continue  # Don't bother printing the empty games

            log(f, "{}:".format(game.name))

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

            log(f, f"\t{spent_on_game} was spent on that game's inventory this year, "
                   f"\t\t{abs(extra_spent)} {more_or_less} than we spent, "
                   f"\t\tso we {affect} {abs(net_counting_inventory)}")

            if collected_on_game_events.amount > 0:
                log(f, f"{collected_on_game_events} was collected on events,"
                       " which could make up for some of that?")

        log(f, "End of report\n\n")
        print(f"Results in '{f.name}'")
        print(f"Detailed results in '{f2.name}'")
        f.close()
