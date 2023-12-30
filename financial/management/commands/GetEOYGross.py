from django.core.management.base import BaseCommand
from moneyed import Money

from checkout.models import Cart
from intake.distributors.utility import log
from partner.models import Partner


class Command(BaseCommand):
    def handle(self, *args, **options):
        year = 2023
        f = open("reports/eoy_gross.txt", "a")
        partner = Partner.objects.get(name__icontains="Valhalla")

        valhalla_subtotal = Money("0", 'USD')
        gross = Money(0, 'USD')
        shipping = Money(0, 'USD')
        tax = Money(0, 'USD')
        total = Money(0, 'USD')
        for cart in Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED], date_paid__year=year) \
                .order_by("date_paid"):
            gross += cart.get_total_subtotal()
            gross += cart.final_ship
            shipping += cart.final_ship
            tax += cart.final_tax
            total += cart.final_total
            valhalla_subtotal += cart.get_subtotal_after_cancellations()
        log(f, "{} was collected gross (net sales tax) in {}".format(gross, year))
        log(f, "{} of that was shipping".format(shipping))
        log(f, "{} was collected in tax ".format(tax))
        log(f, "{} was collected total".format(total))

        log(f, "Valhalla subtotal {} (excluding cancelled lines)".format(valhalla_subtotal))

        log(f, "End of Report\n\n")
        f.close()
