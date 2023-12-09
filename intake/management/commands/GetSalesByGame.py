import csv

from django.core.management.base import BaseCommand
from moneyed import Money

from checkout.models import Cart, CheckoutLine
from game_info.models import Game
from intake.distributors.utility import log
from intake.models import POLine
from inventory_report.management.commands.GetCogs import get_purchased_as, mark_previous_items_as_sold, year
from partner.models import Partner
from shop.models import Product


class Command(BaseCommand):
    # Known bug: If a product is under multiple games, it will mark it as sold by the first game, and then not be
    # available to check for the second game. One way of solving this would be to reset the "sold" count between games.

    def handle(self, *args, **options):
        f = open("reports/earnings by game.txt", "a")
        f2 = open("reports/earnings by game entries.csv", "w")
        detailed_writer = csv.DictWriter(f2, ["Game", "Product", "Quantity", "Cart",
                                              "Collected", "Shipping", "Spent",
                                              "Total Costs", "Net", "Margin",
                                              "POs", "Distributors"])
        partner = Partner.objects.get(name__icontains="CG&T")

        log(f, "End of year Earnings by Game report")
        cart_lines = CheckoutLine.objects.filter(partner_at_time_of_submit=partner,
                                                 cart__status__in=[Cart.PAID, Cart.COMPLETED],
                                                 cart__date_paid__year=year).order_by("cart__date_paid")

        # Cleanup previous purchased as data first
        mark_previous_items_as_sold(f, year)
        po_lines = POLine.objects.filter(po__partner=partner)  # For the get cost calculation.

        for game in Game.objects.all().order_by('name'):
            spent_on_game = Money("0", 'USD')
            spent_on_sold_for_game = Money("0", 'USD')
            shipping_on_game = Money("0", 'USD')
            costs_on_sold_for_game = Money("0", 'USD')
            collected_on_game = Money("0", 'USD')
            log(f, "For {}:".format(game.name))
            for line in cart_lines.filter(item__product__games=game):
                if line.item and line.item.product and line.item.product.barcode:
                    po_out = []
                    spent_on_line = get_purchased_as(line.item.product.barcode, line.quantity, f, line, po_out=po_out)
                    collected_on_line = line.get_subtotal()
                    shipping_on_line = line.get_proportional_postage_paid()
                    costs_on_line = Money(collected_on_line.amount - (spent_on_line.amount + shipping_on_line.amount),
                                          'USD')
                    rowdata = {
                        "Game": game,
                        "Product": line.item.product,
                        "Quantity": line.quantity,
                        "Spent": spent_on_line.amount,
                        "Collected": collected_on_line.amount,
                        "Shipping": shipping_on_line.amount,
                        "Total Costs": costs_on_line.amount,
                        "Net": costs_on_line.amount - collected_on_line.amount,
                        "POs": ", ".join(map(lambda po: str(po), po_out)),
                        "Distributors": ", ".join(map(lambda po: str(po.distributor), po_out)),

                    }
                    if collected_on_line.amount > 0 and costs_on_line.amount > 0:
                        rowdata.update({"Margin": 1 - (costs_on_line.amount / collected_on_line.amount),
                                        })
                    detailed_writer.writerow(rowdata)
                    spent_on_sold_for_game += spent_on_line
                    costs_on_sold_for_game += costs_on_line
                    shipping_on_game += shipping_on_line
                    collected_on_game += collected_on_line
                else:
                    log(f, "{} no longer has an item".format(line))
            product_barcodes = Product.objects.filter(games=game).values_list('barcode', flat=True)
            po_lines = POLine.objects.filter(po__partner=partner, po__date__year=year)
            for line in po_lines.filter(barcode__in=product_barcodes):
                try:
                    spent_on_game += (line.actual_cost * line.expected_quantity)
                except Exception:
                    print("Something is wrong with {}".format(line))

            log(f, "{} was collected from customers".format(collected_on_game))
            log(f, "{} was spent on that inventory, for a net of {}"
                .format(spent_on_sold_for_game,
                        collected_on_game - spent_on_sold_for_game))
            total_net = collected_on_game - spent_on_sold_for_game - shipping_on_game
            log(f, "{} was spent on shipping orders, for a total net of {}"
                .format(shipping_on_game,
                        collected_on_game - spent_on_sold_for_game - shipping_on_game))

            if spent_on_game > total_net:
                affect = "So we overspent {}"
            else:
                affect = "So we made {}"
            log(f, "{} was spent on that game's inventory total, {}"
                .format(spent_on_game,
                        affect.format(abs(total_net - spent_on_game))))

        log(f, "End of report\n\n")
        f.close()
