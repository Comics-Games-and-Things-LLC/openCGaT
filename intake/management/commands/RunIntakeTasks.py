import time
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from dist_backorders.models import BackorderReport
from intake.distributors.nshift import update_tracking_from_nshift
from intake.models import DistributorInventoryFile, PoInvoiceFile, Distributor, DistItem


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            # Run this loop every 30 seconds.
            self.recurring_logic()
            time.sleep(30)

    @staticmethod
    def recurring_logic():
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

        update_tracking_from_nshift()

        # Refresh DistItem products roughly once a day
        items_to_refresh = DistItem.objects.filter(
            Q(product_last_refreshed__isnull=True) |
            Q(product_last_refreshed__lt=timezone.now() - timedelta(days=1))
        ).order_by('product_last_refreshed')[:1000]
        for item in items_to_refresh:
            item.set_product_from_sku()

        # Retrieve Hobbytyme backorders once a day
        hobbytyme = Distributor.objects.filter(dist_name="Hobbytyme").first()
        if hobbytyme:
            last_report = BackorderReport.objects.filter(distributor=hobbytyme).order_by('-retrieved').first()
            if not last_report or last_report.retrieved < timezone.now() - timedelta(days=1):
                try:
                    call_command('load_hobbytyme_backorders')
                except Exception as e:
                    print(f"Error loading Hobbytyme backorders: {e}")

            last_inventory = DistributorInventoryFile.objects.filter(distributor=hobbytyme).order_by(
                '-update_date').first()
            if not last_inventory or last_inventory.update_date < timezone.now() - timedelta(days=1):
                try:
                    call_command('update_hobbytyme_inventory')
                except Exception as e:
                    print(f"Error updating Hobbytyme inventory: {e}")
