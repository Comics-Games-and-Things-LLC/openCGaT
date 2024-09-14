from intake.distributors.utility import log
from partner.models import Partner
from shop.models import InventoryItem


def create_valhalla_item(product, f=None, only_adjust_default_price=False):
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
            if not only_adjust_default_price:
                item.price = price
                log(f, "Price for {} updated to {} (was {}), has barcode {}".format(item, price, item.price,
                                                                                    item.product.barcode))
            else:
                log(f, "Default price for {} updated to {} (was {}), has barcode {}".format(item, price, item.price,
                                                                                            item.product.barcode))
        if item.current_inventory == 0: # If there are none in stock adjust the price anyway.
            item.price = price
        item.default_price = price
        item.save(skip_log=True)
