import time

from django.core.management.base import BaseCommand

from intake.models import DistributorInventoryFile


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            # Run this loop every 30 seconds.
            self.recurring_logic()
            time.sleep(30)

    @staticmethod
    def recurring_logic():
        for inv in DistributorInventoryFile.objects.filter(processed=False):
            inv.run_import()
            inv.processed = True
            inv.save()
