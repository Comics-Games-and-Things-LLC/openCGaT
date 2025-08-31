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
        for item in tqdm(InventoryItem.objects.filter(last_stocked_time__isnull=True)):
            last_log_entry = item.inv_log.latest('timestamp')
            item.last_stocked_time = last_log_entry.timestamp
            item.save()