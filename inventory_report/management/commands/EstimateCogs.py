import datetime

from django.core.management.base import BaseCommand

from inventory_report.management.commands.GetCogs import handle_get_cogs
from partner.models import Partner

partner = Partner.objects.get(name__icontains="Valhalla")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)

    def handle(self, *args, **options):
        year = options.pop('year')  # Last year by default
        if year is None:
            year = datetime.date.today().year - 1
        handle_get_cogs(year, False)


def log(f, string):
    print(string)
    f.write(string + "\n")
