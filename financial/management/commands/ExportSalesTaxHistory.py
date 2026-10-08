import csv
import datetime

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from djmoney.money import Money
from tqdm import tqdm

from checkout.models import Cart
from openCGaT.management_util import email_report
from partner.views import get_address_or_old_address


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)
        parser.add_argument("--month", type=int)
        parser.add_argument("--all", action='store_true')

    def handle(self, *args, **options):

        start_range = None
        end_range = None
        all_time = options.pop("all")
        month = options.pop("month")
        year = options.pop("year")
        if all_time:
            nice_name = f"Sales Tax Report (Start to {datetime.date.today().isoformat()})"
            filename = 'reports/sales_tax_report_{}.csv'.format(datetime.date.today().isoformat())
        elif month:
            if year is None:
                year = datetime.date.today().year
            start_range = datetime.date(year, month, 1)
            end_range = get_last_day_of_month(year, month)
        else:
            ## Default to the previous month.
            start_range, end_range = get_previous_month_range()

        if not all_time:
            nice_name = 'Sales Tax Report from {} to {}'.format(start_range.isoformat(), end_range.isoformat())

            filename = 'reports/sales_tax_report_from_{}_to_{}.csv'.format(start_range.isoformat(),
                                                                           end_range.isoformat())
        with open(filename, 'w',
                  newline='') as csvfile:
            fieldnames = ['Cart Number', 'Contact Info', 'Date Paid', 'Sales Tax Charged', 'Subtotal', 'Shipping',
                          'Pre-Tax Total',
                          'Final Total', "Amount Refunded", "Total Less Refunds", "Cash Paid",
                          'Address',
                          "Cart Status", "Country", "State", 'Date Submitted', "Zip Code"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            carts = Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED],
                                          lost_damaged_or_stolen=False,
                                          broken_down=False,
                                          ).order_by('date_paid')
            if start_range:
                carts = carts.filter(date_paid__gte=start_range)
            if end_range:
                carts = carts.filter(date_paid__lt=end_range)

            pbar = tqdm(total=carts.count(), unit="cart")

            for cart in carts:
                pbar.write("{}: {}".format(cart.id, cart))
                amount_refunded = cart.get_refunded_amount()
                cart_info = {'Cart Number': cart.id, 'Cart Status': cart.status,
                             "Contact Info": cart.owner if cart.owner else cart.email,
                             "Date Paid": cart.date_paid, "Date Submitted": cart.date_submitted,
                             "Subtotal": cart.get_total_subtotal(), "Shipping": cart.final_ship,
                             "Pre-Tax Total": cart.get_final_less_tax(),
                             "Sales Tax Charged": cart.final_tax, "Final Total": cart.final_total,
                             "Amount Refunded": amount_refunded,
                             "Total Less Refunds": cart.final_total - amount_refunded,
                             "Cash Paid": min(cart.cash_paid or Money(0,'USD'), cart.final_total or Money(0,'USD')),
                             }
                country, postcode, potential_address, state = get_address_or_old_address(cart)
                cart_info["Address"] = str(potential_address)
                cart_info["Country"] = country
                cart_info["State"] = state
                cart_info["Zip Code"] = postcode

                writer.writerow(cart_info)
                pbar.update()
            pbar.close()
        print(f"Saved report to {filename}")
        email_report(nice_name, filename)


def get_previous_month_range():
    today = datetime.date.today()
    first_of_this_month = today.replace(day=1)
    last_month = first_of_this_month - datetime.timedelta(days=1)
    return last_month.replace(day=1), first_of_this_month

def get_last_day_of_month(year, month):
    month = month + 1
    if month > 13:
        month = 1
        year = year + 1
    return datetime.date(year, month, 1)-datetime.timedelta(days=1)
