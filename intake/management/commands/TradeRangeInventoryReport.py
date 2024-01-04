from datetime import datetime

from django.core.management.base import BaseCommand

from intake.models import TradeRange
from partner.models import Partner
from shop.models import InventoryItem


class Command(BaseCommand):

    def handle(self, *args, **options):
        f = open("reports/trade range inventory report.txt", "a")
        for tr in TradeRange.objects.all():
            if tr.name != "nan":
                log(f, "\nTR {} {} as of {}".format(tr.distributor, tr.name, datetime.now()))

                for di in tr.contains.all():
                    items = InventoryItem.objects.filter(partner=Partner.objects.get(name__icontains="Valhalla"))
                    items = items.filter(product__barcode=di.dist_barcode) | items.filter(
                        product__publisher_short_sku=di.dist_number)

                    if not items.exists():
                        log(f, f"Does not carry {item}")
                        continue
                    have_stock = False
                    for item in items:
                        if item.current_inventory > 0:
                            have_stock = True
                            break
                    if not have_stock:
                        log(f, f"Out of {di.dist_number} {di.dist_name} ({di.dist_barcode}) ")


def log(f, string):
    print(string)
    f.write(string + "\n")
