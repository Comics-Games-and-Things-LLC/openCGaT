from django.core.management.base import BaseCommand

from intake.distributors import asmodee


class Command(BaseCommand):
    help = 'Loops through imported distributor records'

    def handle(self, *args, **options):
        asmodee.compare_maps()
