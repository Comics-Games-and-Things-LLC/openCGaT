import datetime

from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.postgres.search import SearchQuery
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse

from checkout.models import Cart
from digitalitems.models import DigitalItem
from images.forms import UploadImage
from images.models import Image
from intake.models import DistItem, Distributor
from partner.models import get_partner, get_partner_or_401
from userinfo.forms import UserSelectForm
from .forms import AddProductForm, FiltersForm, AddMTOItemForm, AddInventoryItemForm, \
    CreateCustomChargeForm, RelatedProductsForm, BulkEditItemsForm, ProductsForm
from .models import Product, Item, InventoryItem, MadeToOrder, CustomChargeItem
from .serializers import ItemSerializer, ManageItemSerializer
from .views_api import item_list_filter


def product_list(request, partner_slug=None):
    page_size = 20

    initial_data = {'page_size': page_size}
    site_partner = None
    manage = False
    if partner_slug:
        manage = True
    try:
        if request.site.partner:
            site_partner = request.site.partner
            initial_data["partner"] = site_partner
    except Exception:
        pass
    form = FiltersForm(initial=initial_data, manage=manage)
    manual_form_fields = []
    if len(request.GET) != 0:
        form = FiltersForm(request.GET, initial=initial_data, manage=manage)
    partner = None
    if partner_slug:
        partner = get_partner_or_401(request, partner_slug)
    collection = None
    if form.is_valid():
        collection = form.cleaned_data.get('collection', None)
        categories_to_include = []
        for category in form.cleaned_data.get('categories'):
            categories_to_include += category.get_descendants(
                include_self=True)
        items = item_list_filter(
            managing_partner=partner,
            search_query=form.cleaned_data.get('search'),
            in_stock_only=form.cleaned_data.get('in_stock_only'),
            out_of_stock_only=form.cleaned_data.get('out_of_stock_only'),
            sold_out_only=form.cleaned_data.get('sold_out_only'),
            restock_alert_only=form.cleaned_data.get('restock_alert_only'),
            featured_products_only=form.cleaned_data.get('featured_products_only'),
            price_low=form.cleaned_data.get('price_minimum'),
            price_high=form.cleaned_data.get('price_maximum'),
            publisher=form.cleaned_data.get('publisher'),
            game=form.cleaned_data.get('game'),
            faction=form.cleaned_data.get('faction'),
            distributor=form.cleaned_data.get('distributor'),
            drafts_only=form.cleaned_data.get('drafts_only'),
            missing_image=form.cleaned_data.get('missing_image'),
            categories_to_include=categories_to_include,
            collection=collection,
            order_by=form.cleaned_data.get('order_by'),
            price_not_default=form.cleaned_data.get('price_not_default'),
            has_in_store_only_price=form.cleaned_data.get('has_in_store_only_price'),
            min_qty=form.cleaned_data.get('min_qty'),
            max_qty=form.cleaned_data.get('max_qty'),
        )
    else:
        items = item_list_filter()

    items = items.exclude(customchargeitem__isnull=False)

    if items.count() == 1:
        if partner_slug:
            return HttpResponseRedirect(
                reverse("manage_product", kwargs={'product_slug': items[0].product.slug,
                                                  'partner_slug': partner_slug}))
        return HttpResponseRedirect(
            reverse("product_detail", kwargs={'product_slug': items[0].product.slug}))

    # Handle pageination

    page_number = 1
    if form.is_valid():
        page_size = form.cleaned_data['page_size']
        if page_size is None or page_size <= 1:
            page_size = 20
        page_number = form.cleaned_data['page_number']
        if page_number is None or page_number <= 1:
            page_number = 1

    paginator = Paginator(items, page_size)
    if page_number > paginator.num_pages:
        page_number = 1
    page_obj = paginator.get_page(page_number)

    context = {
        'page': page_obj,
        'filters_form': form,
        'manual_form_fields': manual_form_fields,
        'page_number': int(page_number),
        'partner_slug': partner_slug,
        'manage': manage,
        'collection': collection,
    }
    if partner:
        context['partner'] = partner
    return TemplateResponse(request, "shop/index.html", context=context)


def manage_product_list(request, partner_slug):
    """
    Used to get the list of products (including without items) since the regular search is now just items.
    :param request:
    :param partner_slug:
    :return:
    """
    page_size = 20

    initial_data = {'page_size': page_size}
    manage = True
    form = ProductsForm(initial=initial_data, manage=manage)
    if len(request.GET) != 0:
        form = ProductsForm(request.GET, initial=initial_data, manage=manage)
    partner = get_partner_or_401(request, partner_slug)
    search_query = ""
    categories_to_include = []
    only_templates = False
    publisher = None
    game = None
    faction = None
    distributor = None
    drafts_only = False
    missing_image = False
    collection = None
    products_with_no_items_only = False

    if form.is_valid():
        only_templates = form.cleaned_data.get('templates')
        publisher = form.cleaned_data.get('publisher')
        game = form.cleaned_data.get('game')
        faction = form.cleaned_data.get('faction')
        distributor = form.cleaned_data.get('distributor')
        search_query = form.cleaned_data.get('search')
        for category in form.cleaned_data.get('categories'):
            categories_to_include += category.get_descendants(
                include_self=True)

        products_with_no_items_only = form.cleaned_data.get('products_with_no_items_only')
        drafts_only = form.cleaned_data.get('drafts_only')
        missing_image = form.cleaned_data.get('missing_image')
        collection = form.cleaned_data.get('collection')

    displayed_products = Product.objects.filter()

    if products_with_no_items_only:
        displayed_products = Product.objects.filter(item=None)

    if only_templates:
        displayed_products = displayed_products.filter(page_is_template=True)
    else:
        displayed_products = displayed_products.filter(page_is_template=False)

    if search_query:
        displayed_products = displayed_products.filter(
            Q(name__search=SearchQuery(search_query, search_type='websearch'))
            | Q(barcode=search_query)
            | Q(publisher_short_sku=search_query)
            | Q(publisher_sku=search_query)
            | Q(description__search=SearchQuery(search_query, search_type='websearch'))
        )

    if len(categories_to_include) != 0:
        displayed_products = displayed_products.filter(
            categories__in=categories_to_include)
    if publisher:
        displayed_products = displayed_products.filter(publisher=publisher)
    if game:
        displayed_products = displayed_products.filter(games=game)
    if faction:
        displayed_products = displayed_products.filter(factions=faction)
    if distributor:
        displayed_products = displayed_products.filter(publisher__available_through_distributors=distributor)

    if drafts_only:
        displayed_products = displayed_products.filter(page_is_draft=True)

    if missing_image:
        displayed_products = displayed_products.filter(primary_image__isnull=True)

    if collection:
        displayed_products = displayed_products.filter(in_collection=collection)

    displayed_products = displayed_products.distinct()

    order_by = request.GET.get('order_by', default="-release_date")
    reverse_sort = True if order_by[:1] == '-' else False

    def invert_order_string(order_str):
        return order_str[1:] if order_str.startswith('-') else '-' + order_str

    secondary_sort_string = '-name'
    secondary_order_string = invert_order_string(secondary_sort_string) if reverse_sort else secondary_sort_string

    new_product_list = displayed_products.distinct().order_by(
        order_by, secondary_order_string)

    page_number = 1
    if form.is_valid():
        page_size = form.cleaned_data['page_size']
        if page_size is None or page_size <= 1:
            page_size = 20
        page_number = form.cleaned_data['page_number']
        if page_number is None or page_number <= 1:
            page_number = 1

    paginator = Paginator(new_product_list, page_size)
    if page_number > paginator.num_pages:
        page_number = 1
    page_obj = paginator.get_page(page_number)

    context = {
        'page': page_obj,
        'filters_form': form,
        'page_number': int(page_number),
        'partner': partner,
        'manage': manage,
        'collection': collection,
    }
    return TemplateResponse(request, "partner/product_list.html", context=context)


def get_int_from_request(request, name, default=0):
    """
    Calls request.GET.get on a field that should be an int. Will always return an integer.
    :param request:
    :param name: The name of the parameter eg 'page_number'
    :param default: the default value (defaults to 0). Will be returned if there isn't an int.
    :return: The integer from the request or the default. Always an integer.
    """
    try:
        page_number = request.GET.get(name, default=default)
        page_number = int(page_number)
    except ValueError:
        page_number = 1
    return page_number


def product_details(request, product_slug, partner_slug=None):
    product = get_object_or_404(Product, slug=product_slug)

    partner, manage = get_partner(request, manage_partner_slug=partner_slug)

    inv_items = InventoryItem.objects.filter(product=product)
    download_items = DigitalItem.objects.filter(product=product)
    mto_items = MadeToOrder.objects.filter(product=product)
    custom_items = None
    if partner:
        inv_items = inv_items.filter(partner=partner)
        download_items = download_items.filter(partner=partner)
        mto_items = mto_items.filter(partner=partner)
        custom_items = CustomChargeItem.objects.filter(product=product, partner=partner)

    download_item = download_items.first()

    context = {
        'product': product,
        'inv_items': inv_items,
        'download_item': download_item,
        'mto_items': mto_items,
        'custom_items': custom_items,
    }
    if manage:
        context["partner"] = partner
        context.update(product.get_sold_info(partner=partner))
        context.update(product.get_request_info(partner=partner))

    else:
        if not product.visible:
            raise PermissionDenied

    if manage and product.barcode:
        context["dist_records"] = DistItem.objects.filter(dist_barcode=product.barcode)

    if download_item:
        purchased = download_item.user_already_owns(request.user)
        if purchased:
            if not EmailAddress.objects.filter(
                    user=request.user, verified=True
            ).exists():
                send_email_confirmation(request, request.user)
                return TemplateResponse(request, "account/verified_email_required.html")
        context["di"] = download_item
        if download_item.root_downloadable:
            context["root_folder"] = download_item.root_downloadable.create_dict(user=request.user)

            # context["root_folder"] = {}
            # context["root_folder"]['downloadable'] = DownloadableSerializer(download_item.root_downloadable,
            #                                                context={'user': request.user}).data
        else:
            # context["root_folder"] = None
            context["root_folder"] = {'metadata': None}

        context["purchased"] = purchased
        if partner_slug:
            context['partner'] = partner
            # The following three items are so the upload script knows where to send the file.
            context['partner_slug'] = partner.slug
            context['product_slug'] = product_slug
            context['di_id'] = download_item.id
    return TemplateResponse(request, "shop/product.html", context=context)


def get_item_details(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    return JsonResponse(ItemSerializer(item, context={'cart': request.cart}).data)


@login_required
def manage_product(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    return product_details(request, product_slug, partner_slug=partner_slug)


@login_required
def add_edit_product(request, partner_slug, product_slug=None):
    product = None
    if product_slug:
        product = get_object_or_404(Product, slug=product_slug)
    also_check = []
    if product and not product.all_retail:
        also_check = [product]
    partner = get_partner_or_401(request, partner_slug, also_check)

    form = AddProductForm(instance=product, partner=partner)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AddProductForm(request.POST, instance=product, partner=partner)
        # check whether it's valid:
        print(form.is_valid())
        print(form.errors)
        if form.is_valid():
            new_product = form.save(commit=False)
            new_product.partner = partner
            new_product.save()
            form.save_m2m()
            # redirect to a new URL:
            if 'add_inv' in request.POST:
                return HttpResponseRedirect(
                    reverse("add_inventory_item",
                            kwargs={'partner_slug': partner.slug, 'product_slug': new_product.slug}))
            elif 'add_dig' in request.POST:
                return HttpResponseRedirect(
                    reverse("digital_add_mng", kwargs={'partner_slug': partner.slug, 'product_slug': new_product.slug}))
            elif 'add_mto' in request.POST:
                return HttpResponseRedirect(
                    reverse("add_mto_item", kwargs={'partner_slug': partner.slug, 'product_slug': new_product.slug}))
            else:
                return HttpResponseRedirect(
                    reverse("manage_product", kwargs={'partner_slug': partner.slug, 'product_slug': new_product.slug}))
    context = {
        'form': form,
        'product': product,
        'partner': partner,
        'dist_list': Distributor.objects.filter(dist_name='ACD'),  # Only supporting acd at this time.
    }
    return TemplateResponse(request, "shop/edit_product.html", context=context)


@login_required
def edit_related_products(request, partner_slug, product_slug):
    product = None
    if product_slug:
        product = get_object_or_404(Product, slug=product_slug)
    also_check = []
    if product and not product.all_retail:
        also_check = [product]
    partner = get_partner_or_401(request, partner_slug, also_check)

    form = RelatedProductsForm(instance=product)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = RelatedProductsForm(request.POST, instance=product)
        # check whether it's valid:
        print(form.is_valid())
        print(form.errors)
        if form.is_valid():
            new_product = form.save(commit=False)
            new_product.partner = partner
            new_product.save()
            return HttpResponseRedirect(
                reverse("manage_product", kwargs={'partner_slug': partner.slug, 'product_slug': new_product.slug}))
    context = {
        'form': form,
        'product': product,
        'partner': partner,
    }
    return TemplateResponse(request, "shop/edit_product.html", context=context)


@login_required
def copy_product(request, partner_slug, product_slug, copy_is_replacement=False):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    original_id = product.id  # Cache this for lookup later.
    product_copy = product
    if copy_is_replacement:
        product_copy.name = f"{product.name} [{datetime.date.today().year}]"
    else:
        product_copy.name = f"{product.name} Copy"

    if Product.objects.filter(name=product_copy.name).exists():
        product_copy.name += f" ({product_copy.id})"  # Append ID if this would result in an integrity error.
    product_copy.barcode = None
    product_copy.page_is_draft = True
    product_copy.page_is_template = False
    if not copy_is_replacement:
        product_copy.publisher_sku = None
        product_copy.publisher_short_sku = None
    product_copy.replaced_by = None  # Do not copy "replaced by"

    product_copy.id = None
    product_copy.save()  # Saving gets us a new ID

    product = Product.objects.get(id=original_id)  # Reload original product as product now references product_copy
    # Need to set these attributes manually:
    product_copy.games.add(*product.games.all())
    product_copy.categories.add(*product.categories.all())
    product_copy.editions.set(product.editions.all())
    product_copy.formats.set(product.formats.all())
    product_copy.factions.set(product.factions.all())
    product_copy.attributes.set(product.attributes.all())
    product_copy.save()

    if copy_is_replacement:
        product.replaced_by = product_copy
        product.save()

    return HttpResponseRedirect(
        reverse("edit_product", kwargs={'partner_slug': partner.slug, 'product_slug': product_copy.slug}))


@login_required
def replace_product(request, partner_slug, product_slug):
    return copy_product(request, partner_slug, product_slug, partner_slug)


def delete_product(request, partner_slug, product_slug, confirm):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)

    next_url = reverse("manage_products", kwargs={
        'partner_slug': partner.slug})

    if int(confirm) == 1:
        product.delete()
        return HttpResponseRedirect(next_url)
    else:
        context = {
            'item_name': product.name,
            'confirm_url': reverse('delete_product', kwargs={
                'partner_slug': partner.slug,
                'product_slug': product_slug,
                'confirm': 1,
            }),
            'back_url': next_url,
        }
        return TemplateResponse(request, "confirm_delete.html", context=context)


def upload_primary_image(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    print(request.method)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = UploadImage(request.POST, request.FILES)
        print(form)
        # check whether it's valid:
        if form.is_valid():
            print("Form is valid")
            # process the data in form.cleaned_data as required
            image = form.save(commit=False)
            image.partner = partner
            image.save()
            product.primary_image = image
            product.attached_images.add(image)
            product.save()
            # redirect to a new URL:
            return HttpResponseRedirect(
                reverse("manage_product", kwargs={'partner_slug': partner.slug, 'product_slug': product.slug}))

        else:
            print("form is not valid")
    context = {
        'form': UploadImage(),
        'partner': partner
    }
    return TemplateResponse(request, "create_from_form.html", context=context)


def set_image_as_primary(request, partner_slug, product_slug, image_id):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    image = get_object_or_404(Image, id=image_id)
    product.primary_image = image
    product.save()
    return HttpResponseRedirect(
        reverse("manage_product", kwargs={'partner_slug': partner.slug, 'product_slug': product.slug}))


def upload_additional_image(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    print(request.method)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = UploadImage(request.POST, request.FILES)
        print(form)
        # check whether it's valid:
        if form.is_valid():
            print("Form is valid")
            # process the data in form.cleaned_data as required
            image = form.save(commit=False)
            image.partner = partner
            image.save()
            product.attached_images.add(image)
            product.save()
            # redirect to a new URL:
            return HttpResponseRedirect(
                reverse("manage_product", kwargs={'partner_slug': partner.slug, 'product_slug': product.slug}))

        else:
            print("form is not valid")
    context = {
        'form': UploadImage(),
        'partner': partner
    }
    return TemplateResponse(request, "create_from_form.html", context=context)


def manage_image_upload_endpoint(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    print(request.method)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        with request.FILES['file'] as file:  # There should only be one file
            print(file)
            clean_name = str(file)
            image = Image.objects.create(image_src=file)
            product.attached_images.add(image)
            product.save()
            return HttpResponse(status=200)

    return HttpResponse(status=400)


def remove_image(request, partner_slug, product_slug, image_id):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    try:
        image = get_object_or_404(Image, id=image_id)
        if product.primary_image == image:
            product.primary_image = None
            product.attached_images.remove(image)
            product.save()
        else:
            product.attached_images.remove(image)
    except Exception as e:
        print(e)
    return HttpResponseRedirect(
        reverse("manage_product", kwargs={'partner_slug': partner.slug, 'product_slug': product.slug}))


def account_summary(request):
    context = {
    }
    return TemplateResponse(request, "account/profile.html", context=context)


def why_visibile(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    return JsonResponse({"reason": product.visibility_reason})


@login_required
def add_mto(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    form = AddMTOItemForm()

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AddMTOItemForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            form.instance.partner = partner
            form.instance.product = product
            form.instance.save()
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                                          'product_slug': product_slug}))
    context = {
        'form': form,
        'partner': partner
    }
    return TemplateResponse(request, "create_from_form.html", context=context)


def add_inventory_item(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)

    form = AddInventoryItemForm(partner=partner, product=product)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AddInventoryItemForm(
            request.POST, partner=partner, product=product)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            form.instance.partner = partner
            form.instance.product = product
            form.instance.save()
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                                          'product_slug': product_slug}))
    context = {
        'form': form,
        'partner': partner,
        'product': product,
        'pricing_rule': product.get_price_rule(partner),
        'price_from_rule': product.get_price_from_rule(partner),
        'dist_items': DistItem.find_dist_items(barcode=product.barcode, dist_number=product.publisher_sku),
    }
    return TemplateResponse(request, "shop/edit_inventory_item.html", context=context)


@login_required()
def edit_item(request, partner_slug, product_slug, item_id):
    item = get_object_or_404(Item, id=item_id)

    partner = get_partner_or_401(request, partner_slug)
    if item.partner != partner:
        raise PermissionDenied
    if isinstance(item, InventoryItem):
        form = AddInventoryItemForm(
            instance=item, partner=item.partner, product=item.product)
    if isinstance(item, MadeToOrder):
        form = AddMTOItemForm(instance=item)
    next_url = reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                 'product_slug': product_slug})
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        if isinstance(item, InventoryItem):
            form = AddInventoryItemForm(
                request.POST, instance=item, partner=item.partner, product=item.product)
        elif isinstance(item, MadeToOrder):
            form = AddMTOItemForm(request.POST, instance=item)
        # check whether it's valid:
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(next_url)

    if isinstance(item, InventoryItem):
        product = get_object_or_404(Product, slug=product_slug)

        context = {
            'form': form,
            'partner': partner,
            'product': product,
            'pricing_rule': product.get_price_rule(partner),
            'price_from_rule': product.get_price_from_rule(partner),
            'dist_items': DistItem.find_dist_items(barcode=product.barcode, dist_number=product.publisher_sku),
        }
        return TemplateResponse(request, "shop/edit_inventory_item.html", context=context)
    else:
        context = {"item": item, "form": form, "edit": True, 'partner': partner}
        return TemplateResponse(request, "create_from_form.html", context=context)


@login_required
def delete_item(request, partner_slug, product_slug, item_id, confirm):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    item = get_object_or_404(Item, id=item_id)

    next_url = reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                 'product_slug': product_slug})

    if int(confirm) == 1:
        item.delete()
        return HttpResponseRedirect(next_url)
    else:

        context = {
            'item_name': item.get_type() + " for " + product.name,
            'confirm_url': reverse('delete_item', kwargs={
                'partner_slug': partner.slug,
                'product_slug': product_slug,
                'item_id': item_id,
                'confirm': 1,
            }),
            'back_url': next_url,
        }
        return TemplateResponse(request, "confirm_delete.html", context=context)


@login_required
def create_custom_charge(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    form = CreateCustomChargeForm(partner=partner)
    if request.method == 'POST':
        form = CreateCustomChargeForm(request.POST, partner=partner)
        if form.is_valid():
            custom_charge_item = form.save(commit=False)
            custom_charge_item.partner = partner
            custom_charge_item.default_price = custom_charge_item.price
            if form.cleaned_data['product'] is None:
                custom_charge_item.product, _ = Product.objects.get_or_create(
                    name="Custom Item or Service")
            user = User.objects.get(email=form.cleaned_data['email'])
            print(user)
            custom_charge_item.user = user
            custom_charge_item.save()

            # Add item to user's cart
            cart, _ = Cart.open.get_or_create(owner=user)
            cart.add_item(custom_charge_item)

            # Email user
            custom_charge_item.notify_user_of_custom_charge(cart)

            # Redirect to somewhere useful
        else:
            print("Form not valid")

    context = {
        'partner': partner,
        'form': form,
    }
    return TemplateResponse(request, "create_from_form.html", context=context)


@login_required
def add_to_users_cart(request, partner_slug, product_slug, item_id):
    partner = get_partner_or_401(request, partner_slug)
    item = get_object_or_404(Item, id=item_id)
    error_text = ""
    form = UserSelectForm()
    if request.method == 'POST':
        form = UserSelectForm(request.POST)
        if form.is_valid():
            for user in form.cleaned_data.get('users'):
                # Add item to user's cart
                carts = Cart.open.filter(owner=user)
                if not carts.exists():
                    error_text += f"Could not find cart for {user}. \n"
                # If there are multiple carts, we'll just get the first. Multiple carts should be merged on user login.
                cart = carts.first()
                cart.add_item(item)

                # Email user
                item.notify_user_of_custom_charge(cart)

                # Redirect to somewhere useful
            if not error_text:
                return HttpResponseRedirect(
                    reverse("manage_product",
                            kwargs={'partner_slug': partner.slug, 'product_slug': product_slug}))
        else:
            print("Form not valid")

    context = {
        'partner': partner,
        'form': form,
        'result': error_text,
    }
    return TemplateResponse(request, "create_from_form.html", context=context)


@login_required
def bulk_edit(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)

    initial_data = {'page_size': 20}
    form = BulkEditItemsForm(initial=initial_data, manage=True)
    if len(request.GET) != 0:
        form = BulkEditItemsForm(request.GET, initial=initial_data, manage=True)

    items = Item.objects.none()

    if form.is_valid():
        # Fields I removed: "template" "product_type"
        categories_to_include = []
        for category in form.cleaned_data.get('categories'):
            categories_to_include += category.get_descendants(
                include_self=True)
        items = item_list_filter(
            managing_partner=partner,
            search_query=form.cleaned_data.get('search'),
            in_stock_only=form.cleaned_data.get('in_stock_only'),
            out_of_stock_only=form.cleaned_data.get('out_of_stock_only'),
            sold_out_only=form.cleaned_data.get('sold_out_only'),
            restock_alert_only=form.cleaned_data.get('restock_alert_only'),
            featured_products_only=form.cleaned_data.get('featured_products_only'),
            price_low=form.cleaned_data.get('price_minimum'),
            price_high=form.cleaned_data.get('price_maximum'),
            publisher=form.cleaned_data.get('publisher'),
            game=form.cleaned_data.get('game'),
            faction=form.cleaned_data.get('faction'),
            distributor=form.cleaned_data.get('distributor'),
            drafts_only=form.cleaned_data.get('drafts_only'),
            missing_image=form.cleaned_data.get('missing_image'),
            categories_to_include=categories_to_include,
            order_by=form.cleaned_data.get('order_by'),
            price_not_default=form.cleaned_data.get('price_not_default'),
            has_in_store_only_price=form.cleaned_data.get('has_in_store_only_price'),
            min_qty=form.cleaned_data.get('min_qty'),
            max_qty=form.cleaned_data.get('max_qty'),
        )
        # Update items if action tells us to.
        action = form.cleaned_data.get('action_to_take')
        price_override = form.cleaned_data.get('price')
        multiplier = form.cleaned_data.get('price_multiplier', 1)  # Default to 1 if no value
        base_on_msrp = form.cleaned_data.get('base_on_msrp', False)
        if action == BulkEditItemsForm.UPDATE_PRICES:
            for item in items:
                item.price = get_new_price(item, base_on_msrp, multiplier, price_override)
                item.save()
        if action == BulkEditItemsForm.UPDATE_MSRP:
            for item in items:
                item.price = price_override
                item.save()
        if action == BulkEditItemsForm.SET_IN_STORE_PRICE:
            for item in items:
                item.in_store_only_price = get_new_price(item, base_on_msrp, multiplier, price_override)
                item.save()
        if action == BulkEditItemsForm.CLEAR_IN_STORE_PRICE:
            for item in items:
                item.in_store_only_price = None
                item.save()
        if action == BulkEditItemsForm.UPDATE_BACKORDERS:
            for item in items.instance_of(InventoryItem):  # type: InventoryItem
                item.allow_backorders = form.cleaned_data.get("allow_backorders_update")
                item.save()
        if action == BulkEditItemsForm.ENABLE_ALERT:
            for item in items.instance_of(InventoryItem):  # type: InventoryItem
                item.enable_restock_alert = form.cleaned_data.get("enable_restock_alert")
                item.low_inventory_alert_threshold = form.cleaned_data.get("low_inventory_alert_threshold")
                item.save()

    page_size = 20
    page_number = 1

    if form.is_valid():

        page_size = form.cleaned_data['page_size']
        if page_size is None or page_size <= 1:
            page_size = 20
        page_number = form.cleaned_data['page_number']
        if page_number is None or page_number <= 1:
            page_number = 1

    paginator = Paginator(items, page_size)
    if page_number > paginator.num_pages:
        page_number = 1
    page_obj = paginator.get_page(page_number)
    serialized_list = []
    for item in page_obj.object_list:
        serialized_list.append(ManageItemSerializer(item).data)

    context = {
        'partner': partner,
        'filters_form': form,
        'page': page_obj,  # used only for "has_next_page"
        'serialized_list': serialized_list,
        'page_number': page_number,
        'valid_filter': form.is_valid()
    }
    return TemplateResponse(request, "partner/bulk_change.html", context=context)


def get_new_price(item, base_on_msrp, multiplier, price_override):
    if price_override:
        new_price = price_override
    elif base_on_msrp and item.product.msrp:
        new_price = item.product.msrp * multiplier
    else:
        new_price = item.default_price * multiplier
    return new_price
