from django.core.management.base import BaseCommand

from inventory_report.models import InventoryReport, InventoryReportLine
from partner.models import Partner

partner = Partner.objects.get(name__icontains="Valhalla")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("report_id", type=int)
        parser.add_argument("number", type=int)
        parser.add_argument("barcode", type=str)

    def handle(self, *args, **options):
        number = options.pop('number')
        barcode = options.pop('barcode')
        report_id = options.pop('report_id')

        report = InventoryReport.objects.get(id=report_id, partner=partner)

        for i in range(0, number):
            InventoryReportLine.objects.create(report=report, barcode=barcode)
        print(f"Added {number} to {report}")

