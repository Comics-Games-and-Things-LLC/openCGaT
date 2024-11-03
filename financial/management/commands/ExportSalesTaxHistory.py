import csv
import datetime

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from tqdm import tqdm

from checkout.models import Cart
from partner.views import get_address_or_old_address


class Command(BaseCommand):
    def add_arguments(self, parser):
        # parser.add_argument("--year", type=int)
        # parser.add_argument("--month", type=int)
        parser.add_argument("--all", action='store_true')

    def handle(self, *args, **options):

        start_range = None
        end_range = None
        all_time = options.pop("all")
        nice_name = f"Sales Tax Report {datetime.date.today().isoformat()}"
        filename = 'reports/sales_tax_report_{}.csv'.format(datetime.date.today().isoformat())

        if not all_time:
            start_range, end_range = get_previous_month_range()
            nice_name = 'Sales Tax Report from {} to {}'.format(start_range.isoformat(), end_range.isoformat())

            filename = 'reports/sales_tax_report_from_{}_to_{}.csv'.format(start_range.isoformat(),
                                                                           end_range.isoformat())
        with open(filename, 'w',
                  newline='') as csvfile:
            fieldnames = ['Cart Number', 'Contact Info', 'Date Paid', 'Sales Tax Charged', 'Subtotal', 'Shipping',
                          'Pre-Tax Total',
                          'Final Total', "Amount Refunded", "Total Less Refunds",
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
                             "Amount Refunded": cart.get_refunded_amount(),
                             "Total Less Refunds": cart.final_total - amount_refunded,
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
        email = EmailMessage(nice_name, "Attached is the report", to=[settings.EMAIL_HOST_USER])
        email.attach_file(filename)
        email.send()
        print(f"Emailed to {settings.EMAIL_HOST_USER}")


def get_previous_month_range():
    today = datetime.date.today()
    first_of_this_month = today.replace(day=1)
    last_month = first_of_this_month - datetime.timedelta(days=1)
    return last_month.replace(day=1), first_of_this_month
