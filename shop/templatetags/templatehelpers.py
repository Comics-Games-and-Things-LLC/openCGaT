# Based on this: https://simpleisbetterthancomplex.com/snippet/2016/08/22/dealing-with-querystring-parameters.html
# and this: https://gist.github.com/benbacardi/d6cd0fb8c85e1547c3c60f95f5b2d5e1
from math import floor

from allauth.account.models import EmailAddress
from django import template
from django.conf import settings
from django.db.models import Sum, Q
from django.template import TemplateSyntaxError
from django.template.base import kwarg_re
from django.template.defaulttags import URLNode

from checkout.models import Cart
from digitalitems.models import DigitalItem
from shop.models import Item, InventoryItem, MadeToOrder, CustomChargeItem

register = template.Library()


@register.simple_tag(takes_context=True)
def relative_url(context, value, field_name):
    url = '?{}={}'.format(field_name, value)
    querystring = context['request'].GET.urlencode().split('&')
    filtered_querystring = filter(
        lambda p: p.split('=')[0] != field_name, querystring)
    encoded_querystring = '&'.join(filtered_querystring)
    url = '{}&{}'.format(url, encoded_querystring)
    return url


class ParamURLNode(URLNode):

    def render(self, context):
        url = super(ParamURLNode, self).render(context)
        print(url)
        return '{}?{}'.format(url, context['request'].GET.urlencode())


@register.tag
def keep_get_params_url(parser, token):
    """
    This is a copy of the built-in url tag, but it keeps the querystring parameters from the original URL.
    See django.template.defaulttags.url
    """
    bits = token.split_contents()
    if len(bits) < 2:
        raise TemplateSyntaxError(
            "'%s' takes at least one argument, a URL pattern name." % bits[0]
        )
    viewname = parser.compile_filter(bits[1])
    args = []
    kwargs = {}
    asvar = None
    bits = bits[2:]
    if len(bits) >= 2 and bits[-2] == "as":
        asvar = bits[-1]
        bits = bits[:-2]

    for bit in bits:
        match = kwarg_re.match(bit)
        if not match:
            raise TemplateSyntaxError("Malformed arguments to url tag")
        name, value = match.groups()
        if name:
            kwargs[name] = parser.compile_filter(value)
        else:
            args.append(parser.compile_filter(value))
    url = ParamURLNode(viewname, args, kwargs, asvar)
    return url


@register.simple_tag(takes_context=True)
def site_url(context, cart=None):
    url = ""
    protocol = "https://"
    if settings.DEBUG:
        protocol = "http://"
    if cart and hasattr(cart, 'site'):
        url = cart.site.domain
        # print("using cart's domain")
    else:
        if context and hasattr(context, 'request') and hasattr(context.request, 'site'):
            url = context.request.site.domain
            # print("using requests's domain")
    return protocol + url


@register.simple_tag
def empty_array():
    return []


# used in form rendering
# https://pythoncircle.com/post/701/how-to-set-a-variable-in-django-template/
@register.simple_tag
def list_append(arr, val=None):
    arr.append(val)
    return arr


# https://stackoverflow.com/a/34407158/
@register.simple_tag
def to_list(*args):
    return args


@register.filter
def as_str(value):
    return str(value)


@register.filter
def remove_rendered_fields(fields, rendered_fields):
    return filter(lambda f: f.name not in rendered_fields, fields)


@register.filter
def is_verified(user):
    if not EmailAddress.objects.filter(
            user=user, verified=True
    ).exists():
        return False
    return True


@register.filter
def replace_spaces(spacey_string):
    return spacey_string.replace(" ", "%20")


@register.filter
def multiply(string, times):
    return string * times


@register.filter
def page_range(page_obj, current_page):
    # This code could probably use some clean-up as the off-by one thing is a bit confusing.
    index = current_page - 1  # edited to something easier without index
    # This value is maximum index of your pages, so the last page - 1
    max_index = len(page_obj.paginator.page_range)
    num_of_pages = 7
    half_pages = floor(num_of_pages / 2)
    start_index = index - half_pages if index - half_pages > 0 else 1
    end_index = min(start_index + num_of_pages, max_index - 1)
    return list(page_obj.paginator.page_range)[start_index:end_index]


@register.filter
def page_adjacent(page_number, current_page):
    if page_number == current_page \
            or page_number == current_page - 1 \
            or page_number == current_page + 1:
        return True
    else:
        return False


@register.filter
def page_nearby(page_number, current_page):
    if page_number == current_page \
            or page_number == current_page - 2 \
            or page_number == current_page + 2:
        return True
    else:
        return False


@register.filter
def cart_for_transaction(transaction_id):
    try:
        return Cart.submitted.filter(partner_transactions=transaction_id).first()
    except Exception:
        return None


@register.filter
def customer_for_transaction(transaction):
    if transaction.type == transaction.PURCHASE or transaction.type == transaction.SUBSCRIPTION:
        try:
            cart = Cart.submitted.filter(partner_transactions=transaction).first()
            return cart.owner, cart.email
        except AttributeError:
            return None, None
    return None, None


# this is used in the product list view, see that code in shop/views.py
# for more information about what this filter does
@register.filter()
def items_set_with_custom_manager(product):
    return product.item_set(manager='filtered_items').all().not_instance_of(CustomChargeItem)


@register.filter()
def inventory_items(items):
    return items.instance_of(InventoryItem)


@register.filter()
def download_items(items):
    return items.instance_of(DigitalItem)


@register.filter()
def mto_items(items):
    return items.instance_of(MadeToOrder)


@register.filter()
def get_items_for_partner(item, partner_slug):
    if partner_slug:
        return Item.objects.filter(partner__slug=partner_slug, product=item.product)
    else:
        return Item.objects.filter(product=item.product)


@register.filter()
def get_inv_items_for_partner(product, partner_slug):
    if partner_slug:
        return InventoryItem.objects.filter(partner__slug=partner_slug, product=product)
    else:
        return InventoryItem.objects.filter(product=product)


@register.filter()
def get_download_items_for_partner(product, partner_slug):
    if partner_slug:
        return DigitalItem.objects.filter(partner__slug=partner_slug, product=product)
    else:
        return DigitalItem.objects.filter(product=product)


@register.filter()
def get_mto_items_for_partner(product, partner_slug):
    if partner_slug:
        return MadeToOrder.objects.filter(partner__slug=partner_slug, product=product)
    else:
        return MadeToOrder.objects.filter(product=product)


@register.filter()
def skip_first(array):
    return array[1:]


@register.filter()
def is_inventory_item(item):
    return isinstance(item, InventoryItem)


@register.filter()
def is_download_item(item):
    return isinstance(item, DigitalItem)


@register.filter()
def is_mto_item(item):
    return isinstance(item, MadeToOrder)


@register.filter()
def field_value_or_default(field):
    return field.data if field.data is not None else field.initial


@register.filter()
def get_human_name_by_choice_key(choices, key):
    return choices[get_index_by_choice_key(choices, key)][1]


@register.filter()
def get_index_by_choice_key(choices, key):
    for idx, choice in enumerate(choices):
        if choice[0] == key:
            return idx


@register.filter()
def is_sorted_descending(sort_str):
    return sort_str.startswith('-')


@register.filter()
def is_only_inventory_items(items):
    return items.instance_of(InventoryItem).count() == items.count() and items.count() > 0


@register.filter()
def get_total_inventory(inventory_queryset):
    return \
        inventory_queryset.aggregate(InventoryItem___current_inventory__sum=Sum('InventoryItem___current_inventory'))[
            'InventoryItem___current_inventory__sum']


@register.filter()
def is_backorderable(inventory_queryset):
    return inventory_queryset.filter(InventoryItem___allow_backorders=True).exists()


@register.filter()
def cheapest_item_in_stock(inventory_queryset):
    in_stock_items = inventory_queryset.filter(
        Q(InventoryItem___current_inventory__gte=1))
    if in_stock_items.exists():
        return cheapest_item(in_stock_items)
    else:
        return cheapest_item(inventory_queryset)


@register.filter()
def cheapest_item(item_queryset):
    cheapest = None

    for item in item_queryset:
        if cheapest is None:
            cheapest = item
        else:
            if cheapest.price > item.price:
                cheapest = item
    return cheapest


@register.filter()
def filter_form_bf_props_choice(bound_field):
    return dict(
        choices=bound_field.field.choices,
        currentValue=field_value_or_default(bound_field),
        name=bound_field.name,
        id=bound_field.auto_id,
    )


@register.filter()
def get_retail_partners(user):
    return user.admin_of.filter(retail_partner=True)


@register.filter()
def partner_of_page(product, user):
    return user in product.partner.administrators


@register.filter()
def allowed_to_purchase(item, cart):
    return item.cart_owner_allowed_to_purchase(cart)


@register.filter()
def purchased(item, user):
    return item.user_already_owns(user)
