import datetime

from django.core.management.base import BaseCommand

import traceback

from checkout.models import Cart
from partner.models import Partner, PartnerTransaction


class Command(BaseCommand):
    def handle(self, *args, **options):
        f = open("reports/partner_adjustments.txt", "a")
        for partner in Partner.objects.all().order_by('name'):
            log(f, "{} had balance of {} at {}".format(partner.name, partner.acct_balance, datetime.datetime.now()))
            partner.reset_balance()
            log(f, 'Reset balance for {}'.format(partner.name))
        PartnerTransaction.objects.filter(type=PartnerTransaction.PURCHASE).delete()
        for cart in Cart.submitted.all().order_by('date_paid'):
            cart.pay_partners(suppress_emails=True)
        for partner in Partner.objects.all().order_by('name'):
            partner.update_balance()
            partner.refresh_from_db()
            log(f, "{} has balance of {} at {}".format(partner.name, partner.acct_balance, datetime.datetime.now()))
        f.write("Adjustment complete")
        f.close()


def log(f, string):
    print(string)
    f.write(string + "\n")
