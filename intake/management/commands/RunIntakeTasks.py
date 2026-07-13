import time

from django.core.management.base import BaseCommand

from intake.models import DistributorInventoryFile, PoInvoiceFile
from intake.distributors.nshift import update_tracking_from_nshift


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            # Run this loop every 30 seconds.
            self.recurring_logic()
            time.sleep(30)

    @staticmethod
    def recurring_logic():
        update_tracking_from_nshift()
        for inv in DistributorInventoryFile.objects.filter(processed=False, processing=False):
            inv.processing = True
            inv.save()
            inv.run_import()
            inv.processed = True
            inv.processing = False
            inv.save()
        for inv in PoInvoiceFile.objects.filter(processed=False, processing=False):
            inv.process()
            inv.save()
