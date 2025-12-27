import csv
import os

from django.core.management.base import BaseCommand

from intake.distributors import hobbytyme, kingsley, games_workshop
from intake.models import Distributor
from openCGaT.management_util import email_report


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
        po_object = None
        could_not_process_lines = None
        if not os.path.exists(options['invoice_file']):
            print("Please specify a path to a file that exists")
            return
        if dist == hobbytyme.get_dist_object():
            po, could_not_process_lines = hobbytyme.read_pdf_invoice(options['invoice_file'])
        elif dist == kingsley.get_dist_object():
            po, could_not_process_lines = kingsley.read_pdf_invoice(options['invoice_file'])
        elif dist == games_workshop.get_dist_object():
            po, could_not_process_lines = games_workshop.read_pdf_invoice(options['invoice_file'])
        else:
            print("Not a supported distributor")
        if could_not_process_lines:
            with open('reports/lines_that_could_not_be_processed.csv', 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, could_not_process_lines[0].keys())
                writer.writeheader()
                writer.writerows(could_not_process_lines)

            email_report(f"{po}: {len(could_not_process_lines)} lines that could not be processed",
                         ['reports/lines_that_could_not_be_processed.csv'])
