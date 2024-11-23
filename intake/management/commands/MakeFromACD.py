from django.core.management import BaseCommand

from intake.distributors import acd
from shop.models import Product


class Command(BaseCommand):
    help = "Downloads images from a distributor"

    def add_arguments(self, parser):
        parser.add_argument('upc', type=str)

    def handle(self, *args, **options):
        barcode = options['upc']
        info = acd.query_for_info(barcode, get_full=True)
        print(info)

        product = Product.create_from_dist_info(info)
        print(product, product.id)
