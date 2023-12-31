from datetime import datetime

from django.core.management.base import BaseCommand

import traceback

from django.db.models import Sum

from checkout.models import Cart
from partner.models import Partner, PartnerTransaction


class Command(BaseCommand):
    def handle(self, *args, **options):
        year = 2023
        f = open("reports/partner_tax_info.txt", "a")
        for partner in Partner.objects.all().order_by('name'):
            log(f, "{} for {} generated at {}".format(partner.name, year, datetime.now()))
            transactions = partner.partnertransaction_set.filter(timestamp__year=year)
            total_collected = transactions.filter(type=PartnerTransaction.PURCHASE).aggregate(
                Sum('transaction_subtotal'))['transaction_subtotal__sum']
            log(f, "Gross Sales {}".format(total_collected))
            total_collected = transactions.filter(type=PartnerTransaction.PURCHASE).aggregate(
                Sum('transaction_fees'))['transaction_fees__sum']
            log(f, "Sales Fees {}".format(total_collected))
            total_collected = transactions.filter(type=PartnerTransaction.PAYMENT).aggregate(
                Sum('transaction_subtotal'))['transaction_subtotal__sum']
            log(f, "Total Sent {}".format(total_collected))
            log(f, "\n")

        f.write("End of report\n\n")
        f.close()


def log(f, string):
    print(string)
    f.write(string + "\n")
