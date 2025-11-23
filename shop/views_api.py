from django.contrib.postgres.search import SearchQuery
from django.db.models import F, Q
from moneyed import Money

from shop.forms import FiltersForm
from shop.models import Item


def item_list_filter(managing_partner=None,
                     search_query="",
                     filter_partner_slug=None,
                     price_low=None,
                     price_high=None,
                     categories_to_include=[],
                     filter_partner=None,
                     in_stock_only=False,
                     out_of_stock_only=False,
                     sold_out_only=False,
                     restock_alert_only=False,
                     featured_products_only=None,
                     only_templates=False,
                     publisher=None,
                     game=None,
                     faction=None,
                     distributor=None,
                     drafts_only=False,
                     missing_image=False,
                     collection=None,
                     order_by=None,
                     price_not_default=None,
                     has_in_store_only_price=None,
                     ):
    if order_by is None or order_by == "":
        order_by = "-release_date"
    if price_low is None:
        price_low = Money(0, 'USD')
    if price_high is None:
        price_high = Money(float('inf'), 'USD')

    displayed_items = Item.objects.apply_generic_filters(partner_slug=filter_partner_slug,
                                                         price_low=price_low, price_high=price_high,
                                                         featured=featured_products_only)
    if not managing_partner:
        displayed_items = displayed_items.filter_listed()

    if restock_alert_only:
        displayed_items = displayed_items.filter(inventoryitem__enable_restock_alert=True,
                                                 inventoryitem__current_inventory__lte=F(
                                                     'inventoryitem__low_inventory_alert_threshold'))
    elif in_stock_only:
        displayed_items = displayed_items.filter(
            inventoryitem__current_inventory__gte=1)
    elif out_of_stock_only:
        displayed_items = displayed_items.filter(
            inventoryitem__current_inventory__lte=0, inventoryitem__allow_backorders=True)
    elif sold_out_only:
        displayed_items = displayed_items.filter(
            inventoryitem__current_inventory__lte=0).exclude(inventoryitem__allow_backorders=True)

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
    if distributor:
        displayed_items = displayed_items.filter(product__publisher__available_through_distributors=distributor)
    if drafts_only:
        # Templates are drafts so we have to exclude them as well.
        displayed_items = displayed_items.filter(product__page_is_draft=True, product__page_is_template=False)

    if missing_image:
        displayed_items = displayed_items.filter(product__primary_image__isnull=True)

    if collection:
        displayed_items = displayed_items.filter(product__in_collection=collection)

    if price_not_default:
        displayed_items = displayed_items.exclude(price=F('default_price'))

    if has_in_store_only_price:
        displayed_items = displayed_items.exclude(in_store_only_price__isnull=True)

    displayed_items = displayed_items.distinct()

    if search_query:
        displayed_items = displayed_items.filter(
            Q(product__name__search=SearchQuery(search_query, search_type='websearch'))
            | Q(product__barcode=search_query)
            | Q(product__publisher_short_sku=search_query)
            | Q(product__publisher_sku=search_query)
            | Q(product__description__search=SearchQuery(search_query, search_type='websearch'))
        )

    # Handle ordering.
    reverse_sort = True if order_by[:1] == '-' else False

    def invert_order_string(order_str):
        return order_str[1:] if order_str.startswith('-') else '-' + order_str

    # Take the reverse off temporarily, re-apply at the end
    if order_by.startswith('-'):
        order_by = order_by[1:]

    if order_by not in [option[0] for option in FiltersForm.SORT_OPTIONS]:  # get keys from tuple
        raise ValueError("Unsupported sort method")

    # For the last stocked sort, exclude items without this property set.
    if order_by == FiltersForm.SORT_LAST_STOCKED.lstrip("-"):
        displayed_items = displayed_items \
            .exclude(inventoryitem__last_stocked_time__isnull=True) \
            .exclude(inventoryitem__isnull=True)

    # Map these values to the actual fields
    if order_by == FiltersForm.SORT_ALPHABETICAL.lstrip("-"):
        order_by = 'product__name'
    elif order_by == FiltersForm.SORT_RELEASE_DATE.lstrip("-"):
        order_by = 'product__release_date'
    elif order_by == FiltersForm.SORT_LAST_STOCKED.lstrip("-"):
        order_by = 'inventoryitem__last_stocked_time'

    # print(order_by)

    # re-apply reverse
    if reverse_sort:
        order_by = '-' + order_by

    secondary_sort_string = '-product__name'
    secondary_order_string = invert_order_string(secondary_sort_string) if reverse_sort else secondary_sort_string

    return displayed_items.prefetch_related('partner', 'product').order_by(
        order_by, secondary_order_string)


def get_item_list(request, partner_slug=None):
    # To eventually replace product_list
    return
