from decimal import Decimal

import moneyed
from django.core.management.base import BaseCommand
from moneyed import Money
from tqdm import tqdm

from checkout.models import Cart
from intake.distributors.utility import log
from partner.models import Partner


class Command(BaseCommand):
    def handle(self, *args, **options):
        year = 2023
        f = open(f"reports/eoy_gross_{year}.txt", "a")
        partner = Partner.objects.get(name__icontains="Valhalla")

        valhalla_subtotal = Money("0", 'USD')
        gross = Money(0, 'USD')
        shipping = Money(0, 'USD')
        tax = Money(0, 'USD')
        total = Money(0, 'USD')
        total_collected = Money(0, 'USD')
        for cart in tqdm(Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED], date_paid__year=year)
                                 .order_by("date_paid")):
            gross += cart.get_total_subtotal()
            gross += cart.final_ship
            shipping += cart.final_ship
            tax += cart.final_tax
            total += cart.final_total
            valhalla_subtotal += cart.get_subtotal_after_cancellations()
            try:
                if cart.total_paid:
                    if cart.total_paid.amount > (cart.final_total.amount + Decimal(.01)):
                        log(f, f"{cart} was overpaid, we likely gave change")
                    if cart.total_paid.amount < (cart.final_total.amount - Decimal(.01)):
                        log(f, f"{cart} was underpaid!")

                # Use the minimum of final total and total paid,
                total_collected += min(cart.final_total, cart.total_paid or Money(0, 'USD'))
            except moneyed.classes.CurrencyDoesNotExist:
                pass  # If total_paid is not set, currency will be XYZ, which crashes moneyed

        log(f, "{} was collected gross (net sales tax) in {}".format(gross, year))
        log(f, "{} of that was shipping".format(shipping))
        log(f, "{} was collected in tax ".format(tax))
        log(f, "{} was theoretically collected total".format(total))
        log(f, "{} was actually collected total".format(total))

        log(f, "Valhalla subtotal {} (excluding cancelled lines)".format(valhalla_subtotal))

        log(f, "End of Report\n\n")
        f.close()
