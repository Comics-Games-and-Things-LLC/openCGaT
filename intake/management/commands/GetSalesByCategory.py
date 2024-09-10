from django.core.management.base import BaseCommand

from intake.management.commands.GetSalesByGame import get_sales_by_thing, CATEGORY


class Command(BaseCommand):

    # Update year in GetCogs

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int)
        parser.add_argument("--all", action='store_true')

    def handle(self, *args, **options):
        get_sales_by_thing(CATEGORY, **options)
