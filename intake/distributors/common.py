from intake.distributors.utility import log
from partner.models import Partner
from shop.models import InventoryItem


def create_valhalla_item(product, f=None):
    if f is None:
        f = open("reports/valhalla_inventory_price_adjustments.txt", "a")

    partner = Partner.objects.get(name__icontains="Valhalla")

    price = product.get_price_from_rule(partner)
    if price:
        item, created = InventoryItem.objects.get_or_create(partner=partner,
                                                            product=product,
                                                            defaults={
                                                                'price': price, 'default_price': price
                                                            })
        if price != item.price and item.current_inventory > 0:
            log(f, "Price for {} updated to {} (was {}), has barcode {}".format(item, price, item.price,
                                                                                item.product.barcode))
        item.price = price
        item.default_price = price
        item.save()
