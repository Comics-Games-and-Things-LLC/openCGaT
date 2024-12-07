import os

from django.core.management.base import BaseCommand

from intake.distributors import hobbytyme, kingsley
from intake.models import Distributor


class Command(BaseCommand):
    help = "Read a pdf from a distributor"

    def add_arguments(self, parser):
        parser.add_argument('distributor', type=str)
        parser.add_argument('invoice_file', type=str)

    def handle(self, *args, **options):
        dists = Distributor.objects.filter(dist_name__search=options['distributor'])
        dist = None
        if dists.count() == 1:
            dist = dists.first()
            print(dist)
        else:
            print("Please choose a distributor:")
            print(dists)
            return

        if not os.path.exists(options['invoice_file']):
            print("Please specify a path to a file that exists")
            return
        if dist == hobbytyme.get_dist_object():
            hobbytyme.read_pdf_invoice(options['invoice_file'])
        if dist == kingsley.get_dist_object():
            kingsley.read_pdf_invoice(options['invoice_file'])
        else:
            print("Not a supported distributor")
