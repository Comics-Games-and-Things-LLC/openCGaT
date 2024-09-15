from django.core.management.base import BaseCommand

from intake.distributors import vallejo, acd
from intake.models import *


class Command(BaseCommand):
    help = "Downloads images from a distributor"

    def add_arguments(self, parser):
        parser.add_argument('Distributor', type=str)

    def handle(self, *args, **options):
        search = options['Distributor']
        if not search:
            print("Please specify distributor")
            return
        if search == "Vallejo":
            vallejo.download_images()
            exit()
        dists = Distributor.objects.filter(dist_name__search=search)
        dist = None
        if dists.count() == 1:
            dist = dists.first()
            print(dist)
        else:
            print("Please choose a distributor:")
            print(dists)
            return
        name = dist.dist_name
        if name == acd.dist_name:
            acd.download_images()
        else:
            print("Import not set up for that distributor")
