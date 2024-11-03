from django.core.management import BaseCommand

from intake.distributors import acd


class Command(BaseCommand):
    help = "Downloads images from a distributor"

    def add_arguments(self, parser):
        parser.add_argument('upc', type=str)

    def handle(self, *args, **options):
        search = options['upc']
        info = acd.query_for_info(search, get_full=True)
        print(info)
