import datetime

import stripe
from django.core.management.base import BaseCommand

from payments.models import Payment


class Command(BaseCommand):

    def handle(self, *args, **options):
        filename = 'reports/refund_report_report_{}.csv'.format(datetime.date.today().isoformat())

        for payment in Payment.objects.all():
            refund_amount = None
            try:
                refund_amount = payment.get_refunded_amount()
            except stripe.error.InvalidRequestError:
                pass
                # print("You attempted to access a payment request from live mode in test mode")
            if refund_amount:
                print(refund_amount)




