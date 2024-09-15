from django.core.management.base import BaseCommand

from intake.distributors import parabellum, wyrd, games_workshop, gw_paints, vallejo, asmodee
from intake.models import *


class Command(BaseCommand):
    help = "imports the inventory from a distributor"

    def add_arguments(self, parser):
        parser.add_argument('Distributor', type=str)

    def handle(self, *args, **options):
        search = options['Distributor']
        if not search:
            print("Please specify distributor")
            return
        if search == "Citadel":
            gw_paints.import_records()
            exit()
        if search == "Vallejo":
            vallejo.import_records()
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
        if name == wyrd.dist_name:
            wyrd.import_records()
        elif name == games_workshop.dist_name:
            games_workshop.import_records()
        elif name == parabellum.dist_name:
            parabellum.import_records()
        elif name == asmodee.dist_name:
            asmodee.import_records()
        else:
            print("Import not set up for that distributor")
