import datetime
import stripe

from django.core.management.base import BaseCommand

from payments.models import Payment


class Command(BaseCommand):

    def handle(self, *args, **options):
        filename = 'reports/refund_report_report_{}.csv'.format(datetime.date.today().isoformat())

        with open(filename, 'w'):
            for intent in stripe.Refund.list():
                print()





