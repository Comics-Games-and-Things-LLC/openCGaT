import csv
import datetime

from django.core.management.base import BaseCommand

from checkout.models import Cart
from partner.views import get_address_or_old_address


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open('reports/sales_tax_report_{}.csv'.format(datetime.date.today().isoformat()), 'w',
                  newline='') as csvfile:
            fieldnames = ['Cart Number', 'Contact Info', 'Date Paid', 'Sales Tax Charged', 'Subtotal', 'Shipping',
                          'Pre-Tax Total',
                          'Final Total', "Amount Refunded", "Total Less Refunds",
                          'Address',
                          "Cart Status", "Country", "State", 'Date Submitted', "Zip Code"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for cart in Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED],
                                              lost_damaged_or_stolen=False,
                                              broken_down=False,
                                              ).order_by('date_paid'):
                print("{}: {}".format(cart.id, cart))
                amount_refunded = cart.get_refunded_amount()
                cart_info = {'Cart Number': cart.id, 'Cart Status': cart.status,
                             "Contact Info": cart.owner if cart.owner else cart.email,
                             "Date Paid": cart.date_paid, "Date Submitted": cart.date_submitted,
                             "Subtotal": cart.get_total_subtotal(), "Shipping": cart.final_ship,
                             "Pre-Tax Total": cart.get_final_less_tax(),
                             "Sales Tax Charged": cart.final_tax, "Final Total": cart.final_total,
                             "Amount Refunded": cart.get_refunded_amount(),
                             "Total Less Refunds": cart.final_total - amount_refunded,
                             }
                country, postcode, potential_address, state = get_address_or_old_address(cart)
                cart_info["Address"] = str(potential_address)
                cart_info["Country"] = country
                cart_info["State"] = state
                cart_info["Zip Code"] = postcode

                writer.writerow(cart_info)
