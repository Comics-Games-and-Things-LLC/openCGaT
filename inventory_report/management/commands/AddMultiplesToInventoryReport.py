from django.core.management.base import BaseCommand

from inventory_report.models import InventoryReport, InventoryReportLine, InventoryReportLocation
from partner.models import Partner

partner = Partner.objects.get(name__icontains="Valhalla")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("year", type=int)
        parser.add_argument("location", type=str)
        parser.add_argument("number", type=int)
        parser.add_argument("barcode", type=str)

    def handle(self, *args, **options):
        year = options.pop('year')
        location_str = options.pop('location')
        number = options.pop('number')
        barcode = options.pop('barcode')

        report = InventoryReport.objects.get(date__year=year, partner=partner)
        location = InventoryReportLocation.objects.get(partner=partner, name__icontains=location_str)

        for i in range(0, number):
            InventoryReportLine.objects.create(report=report, barcode=barcode, location=location)
        print(f"Added {number} to {report}")

