import time

from django.core.management.base import BaseCommand

from intake.distributors.acd_armypainter import query_for_info
from intake.models import *
from shop.models import Publisher, InventoryItem


class Command(BaseCommand):
    help = "Download Army Painter Fanatic from ACD"

    def handle(self, *args, **options):
        category = Category.objects.get(id=2337)
        publisher = Publisher.objects.get(name="Army Painter")
        partner = Partner.objects.get(name__icontains="Valhalla")

        for i in range(1, 217):
            sku = f"AMYWP3{str(i).rjust(3, '0')}"
            print(sku)
            try:
                if Product.objects.filter(publisher_sku=sku).exists():
                    product = Product.objects.get(publisher_sku=sku)
                else:
                    time.sleep(1)
                    info = query_for_info(sku, debug=False)
                    product = Product.create_from_dist_info(info)
            except Exception as e:
                print(e)
                continue
            product.publisher = publisher
            product.categories.add(category)
            product.page_is_draft = False
            product.visible_on_release = True
            product.listed_on_release = True
            product.purchasable_on_release = True
            product.save()
            price = product.get_price_from_rule(partner)

            item, created = InventoryItem.objects.get_or_create(partner=partner,
                                                                product=product,
                                                                defaults={
                                                                    'price': price, 'default_price': price
                                                                })
            if not created:
                item.price = price
                item.default_price = price
            item.allow_backorders = False
            item.enable_restock_alert = True
            item.low_inventory_alert_threshold = 1
            item.save()
