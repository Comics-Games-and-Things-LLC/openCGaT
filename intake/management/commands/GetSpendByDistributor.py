import csv
import datetime
import os

from django.core.management.base import BaseCommand
from django.db.models import Sum

from intake.models import Distributor, PurchaseOrder
from openCGaT.management_util import email_report


class Command(BaseCommand):

    # Update year in GetCogs

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)
        parser.add_argument("--all", action='store_true')

    def handle(self, *args, **options):
        year = options.pop('year')  # Last year by default
        if year is None:
            year = datetime.date.today().year - 1
        all_time = options.pop("all")
        if all_time:
            year = None
        display_year = year
        if year is None:
            display_year = "all time"

        report_name = f"Spend by distributor for {display_year}"
        filename = f"{report_name}.csv"

        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['Distributor', 'Total Subtotal', 'Currency', 'Total Amount Charged (USD)']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for distributor in Distributor.objects.all().order_by('dist_name'):
                pos = PurchaseOrder.objects.filter(distributor=distributor)
                if year:
                    pos = pos.filter(date__year=year)
                
                # MoneyField aggregation is tricky in Django, so we'll sum manually or use aggregate if possible.
                # Since it's a MoneyField, 'subtotal' column in DB is usually 'subtotal' (amount) and 'subtotal_currency'.
                # We can aggregate the amount since we're filtering by distributor (single currency).
                aggregates = pos.aggregate(
                    total_subtotal=Sum('subtotal'),
                    total_charged=Sum('amount_charged')
                )
                total_subtotal = aggregates['total_subtotal'] or 0
                total_charged = aggregates['total_charged'] or 0
                
                writer.writerow({
                    'Distributor': distributor.dist_name,
                    'Total Subtotal': total_subtotal,
                    'Currency': distributor.currency,
                    'Total Amount Charged (USD)': total_charged,
                })

        email_report(report_name, filename)
        os.remove(filename)
