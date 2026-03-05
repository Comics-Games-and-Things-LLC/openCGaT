from django.core.management.base import BaseCommand

from intake.distributors import games_workshop
from intake.models import DistributorInventoryFile


class Command(BaseCommand):
    def handle(self, *args, **options):
        for inv in DistributorInventoryFile.objects.filter(processed=False):
            inv.run_import()
            inv.processed = True
            inv.save()



