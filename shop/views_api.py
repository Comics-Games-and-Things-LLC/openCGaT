from moneyed import Money

from shop.models import Item


def item_list_filter(managing_partner=None,
                     search_query="",
                     filter_partner_slug=None,
                     price_low=None,
                     price_high=None,
                     categories_to_include=None,
                     filter_partner=None,
                     in_stock_only=False,
                     out_of_stock_only=False,
                     sold_out_only=False,
                     featured_products_only=None,
                     only_templates=False,
                     publisher=None,
                     game=None,
                     faction=None,
                     ):
    if price_low is None:
        price_low = Money(0, 'USD')
    if price_high is None:
        price_high = Money(float('inf'), 'USD')

    # displayed_items = Item.objects.none()
    displayed_items = Item.objects.apply_generic_filters(partner_slug=filter_partner_slug,
                                                         price_low=price_low, price_high=price_high,
                                                         featured=featured_products_only)
    if not managing_partner:
        displayed_items = displayed_items.filter_listed()

    # Don't apply these filters unless there is a value, otherwise we'll be doing a search for blanks.
    if len(categories_to_include) != 0:
        displayed_items = displayed_items.filter(
            product__categories__in=categories_to_include)
    if publisher:
        displayed_items = displayed_items.filter(product__publisher=publisher)
    if game:
        displayed_items = displayed_items.filter(product__games=game)
    if faction:
        displayed_items = displayed_items.filter(product__factions=faction)
    displayed_items = displayed_items.distinct()

    return displayed_items
