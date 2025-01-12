import csv
import datetime
from decimal import Decimal

import moneyed
from django.core.management.base import BaseCommand
from moneyed import Money
from tqdm import tqdm

from checkout.models import Cart
from intake.distributors.utility import log
from openCGaT.management_util import email_report
from payments.models import StripePayment, PaypalPayment


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)

    def handle(self, *args, **options):
        year = options.pop('year')  # Last year by default
        if year is None:
            year = datetime.date.today().year - 1

        log_filename = f"reports/eoy_gross_{year}.txt"
        f = open(log_filename, "w")

        not_cancelled_subtotal = Money("0", 'USD')
        shipping = Money(0, 'USD')
        tax = Money(0, 'USD')
        total = Money(0, 'USD')
        total_collected = Money(0, 'USD')
        stripe_collected = Money(0, 'USD')
        paypal_collected = Money(0, 'USD')
        total_cancellations = Money(0, 'USD')
        csv_filename = 'reports/eoy_gross_{}.csv'.format(year)

        with open(csv_filename, 'w',
                  newline='') as csvfile:
            fieldnames = ['Cart', 'final_total', 'subtotal', 'subtotal_after_cancellations', 'collected',
                          'cancellations', 'stripe', 'paypal', 'payments']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for cart in tqdm(Cart.submitted.filter(date_paid__year=year)  # Include cancelled carts
                                     .order_by("date_paid")):
                subtotal = cart.get_total_subtotal()
                subtotal_after_cancellations = cart.get_subtotal_after_cancellations()
                cancellations = subtotal - subtotal_after_cancellations
                row_data = {"Cart": cart.id,
                            "Status": cart.status,
                            'subtotal': subtotal,
                            'final_total': cart.final_total,
                            'subtotal_after_cancellations': subtotal_after_cancellations,
                            'cancellations': cancellations
                            }
                shipping += cart.final_ship
                tax += cart.final_tax
                total += cart.final_total
                total_cancellations += cancellations
                not_cancelled_subtotal += subtotal_after_cancellations
                try:
                    if cart.total_paid:
                        if cart.total_paid.amount > (cart.final_total.amount + Decimal(.01)):
                            pass # Stopped logging these overpaid messages since they're mostly from giving change.
                            # log(f, f"{cart} was overpaid, we likely gave change")
                        if cart.total_paid.amount < (cart.final_total.amount - Decimal(.01)):
                            log(f, f"{cart} was underpaid!")

                    # Use the minimum of final total and total paid,
                    total_collected += min(cart.final_total, cart.total_paid or Money(0, 'USD'))
                    row_data['collected'] = min(cart.final_total, cart.total_paid or Money(0, 'USD'))
                except moneyed.classes.CurrencyDoesNotExist:
                    pass  # If total_paid is not set, currency will be XYZ, which crashes moneyed

                stripe_payments_for_cart_total = Money(0, 'USD')
                paypal_payments_for_cart_total = Money(0, 'USD')
                payments = []
                for payment in cart.payments.all():
                    payments.append(str(payment))
                    if payment.collected:
                        if type(payment) is StripePayment:
                            stripe_payments_for_cart_total += payment.requested_payment
                        if type(payment) is PaypalPayment:
                            paypal_payments_for_cart_total += payment.requested_payment

                for payment in cart.stripepaymentintent_set.all():
                    payments.append(str(payment))
                    if payment.captured:
                        stripe_payments_for_cart_total += payment.amount_to_pay

                row_data['stripe'] = stripe_payments_for_cart_total
                stripe_collected += stripe_payments_for_cart_total
                row_data['paypal'] = paypal_payments_for_cart_total
                paypal_collected += paypal_payments_for_cart_total
                row_data['payments'] = payments

                writer.writerow(row_data)

        log(f, "{} was collected total (including cancellations)".format(total_collected))
        log(f, "{} of that was shipping charges".format(shipping))
        log(f, "{} of that was sales tax".format(tax))

        log(f, f"{stripe_collected} was collected from Stripe.")
        log(f, f"{paypal_collected} was collected from Paypal" +
            " (through the website, not counting people just sending us money).")
        log(f, f"{total_collected - stripe_collected - paypal_collected} was thus" +
            " probably collected in cash, paypal direct, or bank transfers ")

        log(f, "This report does not handle refunds very well." +
            " It doesn't know if we refunded that order or if it was used as credit for another item, "
            "or maybe never collected payment for that order at all." +
            " That's why we should get the amount refunded from the payment processors.")
        log(f, f"{not_cancelled_subtotal} was the total subtotal from customers that was not cancelled.")
        log(f, f"{total_cancellations} was the total of cancelled items" +
            " (and thus the max we could have possibly refunded)")

        log(f, "End of Report\n\n")
        f.close()
        email_report(f"EOY Gross {year}", [log_filename, csv_filename])
