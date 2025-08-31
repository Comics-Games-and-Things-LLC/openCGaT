from django.core.management.base import BaseCommand
from tqdm import tqdm

from shop.models import InventoryItem


class Command(BaseCommand):
    # Known bug: If a product is under multiple games, it will mark it as sold by the first game, and then not be
    # available to check for the second game. One way of solving this would be to reset the "sold" count between games.

    def add_arguments(self, parser):
        pass
        # parser.add_argument("--year", type=int)
        # parser.add_argument("--all", type=bool)

    def handle(self, *args, **options):
        for item in tqdm(InventoryItem.objects.all()):
            intake_log = item.inv_log.filter(change_quantity__gt=0)
            if intake_log.exists():
                item.last_stocked_time = intake_log.latest('timestamp').timestamp
            else:
                item.last_stocked_time = None
            item.save()
