import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone

from intake.models import DistributorInventoryFile, PoInvoiceFile, Distributor
from intake.distributors.nshift import update_tracking_from_nshift
from dist_backorders.models import BackorderReport


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            # Run this loop every 30 seconds.
            self.recurring_logic()
            time.sleep(30)

    @staticmethod
    def recurring_logic():
        update_tracking_from_nshift()

        # Retrieve Hobbytyme backorders once a day
        hobbytyme = Distributor.objects.filter(dist_name="Hobbytyme").first()
        if hobbytyme:
            last_report = BackorderReport.objects.filter(distributor=hobbytyme).order_by('-retrieved').first()
            if not last_report or last_report.retrieved < timezone.now() - timedelta(days=1):
                try:
                    call_command('load_hobbytyme_backorders')
                except Exception as e:
                    print(f"Error loading Hobbytyme backorders: {e}")

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
