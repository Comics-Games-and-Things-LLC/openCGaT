import datetime

from allauth.account.decorators import verified_email_required
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from digitalitems.forms import *
from partner.models import get_partner_or_401
from shop.models import Product


@verified_email_required
def account_downloads(request, refresh=0):
    page_size = 10
    site_partner = None
    initial_data = {'page_size': page_size}
    if request.user.is_authenticated:
        # First ensure that all purchases are imported
        # Now check all purchases
        downloads = DigitalItem.objects.filter(downloads__in=request.user.downloads.all()).distinct()
        print(downloads)
        form = FiltersForm(initial=initial_data)
        if len(request.GET) != 0:
            form = FiltersForm(request.GET, initial=initial_data)

        if form.is_valid():
            print(form.cleaned_data)

            if form.cleaned_data.get('search'):
                search_query = form.cleaned_data.get('search')
                if search_query:
                    downloads = downloads.filter(
                        product__name__search=SearchQuery(search_query, search_type='websearch'))
            if form.cleaned_data.get('partner'):
                partner_slug = request.GET.get('partner', default='')
                downloads = downloads.filter(partner__slug=partner_slug)
            if form.cleaned_data.get('categories'):
                categories_to_include = []
                for category in form.cleaned_data.get('categories'):
                    categories_to_include += category.get_descendants(include_self=True)
                if len(categories_to_include) != 0:
                    downloads = downloads.filter(
                        product__categories__in=categories_to_include)

        order_by = request.GET.get('order_by', default="-product__release_date")
        reverse_sort = True if order_by[:1] == '-' else False

        def invert_order_string(order_str):
            return order_str[1:] if order_str.startswith('-') else '-' + order_str

        secondary_sort_string = '-product__name'
        secondary_order_string = invert_order_string(secondary_sort_string) if reverse_sort else secondary_sort_string

        downloads = downloads.distinct().order_by(order_by, secondary_order_string)

        page_number = 1
        if form.is_valid():
            page_size = form.cleaned_data['page_size']
            if page_size is None or page_size <= 1:
                page_size = 10
            page_number = form.cleaned_data['page_number']
            if page_number is None or page_number <= 1:
                page_number = 1

        paginator = Paginator(downloads, page_size)  # Show 10 contacts per page.
        page = paginator.get_page(page_number)
        print(page.count)
        print(page.object_list)
        download_list = {}
        for di in page:
            if di.root_downloadable:
                download_list[di] = di.root_downloadable.create_dict(user=request.user)
        context = {
            'download_list': download_list,
            "purchased": True,
            'filters_form': form,
            'page': page,
            'page_number': page_number,
            'manual_form_fields': []
        }
        return TemplateResponse(request, "digital/downloads.html", context=context)

    else:
        return redirect("account_login")


@login_required
def add_digital(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AddEditDigital(request.POST, partner=partner)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            form.save(partner=partner, product=product)
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                                          'product_slug': product_slug}))
    context = {
        'form': AddEditDigital(partner=partner),
        'partner': partner
    }
    return TemplateResponse(request, "create_from_form.html", context=context)


@login_required
def edit_digital(request, partner_slug, product_slug, di_id, ):
    di = get_object_or_404(DigitalItem, id=di_id)
    product = get_object_or_404(Product, slug=product_slug)
    partner = get_partner_or_401(request, partner_slug, [product])
    if di.partner != partner:
        raise PermissionDenied
    form = AddEditDigital(instance=di, partner=partner)
    next_url = reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                 'product_slug': product_slug})
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AddEditDigital(request.POST, instance=di, partner=partner)
        # check whether it's valid:
        if form.is_valid():
            form.save(partner=partner, product=product)
            return HttpResponseRedirect(next_url)

    purchased = di.user_already_owns(request.user)

    context = {"di": di, "purchased": purchased, "form": form, "edit": True, 'partner': partner,
               'digital_item_form': AddEditDigital(partner=partner),
               'partner_slug': partner.slug, 'product_slug': product_slug, 'di_id': di_id}
    # The following three items are so the upload script knows where to send the file.

    return TemplateResponse(request, "digital/digital_edit.html", context=context)


@login_required
def delete_digital(request, partner_slug, product_slug, di_id, confirm):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    di = get_object_or_404(DigitalItem, id=di_id)

    next_url = reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                 'product_slug': product_slug})

    if int(confirm) == 1:
        di.delete()
        return HttpResponseRedirect(next_url)
    else:

        context = {
            'item_name': "Digital Version of " + product.name,
            'confirm_url': reverse('digital_delete_mng', kwargs={
                'partner_slug': partner.slug,
                'product_slug': product_slug,
                'di_id': di_id,
                'confirm': 1,
            }),
            'back_url': next_url,
        }
        return TemplateResponse(request, "confirm_delete.html", context=context)


@verified_email_required
def download(request, di_id, di_file_id):
    di_file = get_object_or_404(DIFile, id=di_file_id)
    di = get_object_or_404(DigitalItem, id=di_id)
    if request.user not in di.partner.administrators.all():  # a partner can always download their own files
        # If it's not a partner then do additional checks
        if not di.available_for_download():
            raise PermissionDenied
        if di not in di_file.digitalitem_set.all():
            raise PermissionDenied
        if not di.user_already_owns(request.user):
            raise PermissionDenied
    history_record = di_file.log_download(request.user)
    data = {
        'comment_stamp': "Downloaded by {} on {}. Created by {}".format(request.user.email,
                                                                        history_record.timestamp,
                                                                        di.partner),
        'seed1': di_file.azure_file.url,
        'seed2': di_file.b2_file.url,
        'userid': request.user.id,
        'tz': di.tag_zip_files,
        'to': di.tag_obj_files,
        'clean_name': di_file.clean_name,
    }
    return JsonResponse(data)


@login_required
def download_multi(request, di_id, downloadable_id):
    """
    :param request:
    :param downloadable_id:
    :return: JSON containing a list of all the files that are in the folder downloadable_id
    """
    di = get_object_or_404(DigitalItem, id=di_id)
    if request.user not in di.partner.administrators.all():  # a partner can always download their own files
        # If it's not a partner then do additional checks
        if not di.available_for_download():
            raise PermissionDenied
        if not di.user_already_owns(request.user):
            raise PermissionDenied
    downloadable = get_object_or_404(Downloadable, id=downloadable_id)
    files_to_download = downloadable.get_download_info()
    payload = {'files_to_download': files_to_download,
               'di_id': di_id,
               }
    return JsonResponse(payload)


@login_required
@transaction.atomic
def upload_file(request, partner_slug, product_slug, di_id, parent_node_id):
    di, partner = verify_user_can_edit(di_id, partner_slug, request)

    parent_node = get_object_or_404(Downloadable, id=parent_node_id)

    print(request.POST)
    print(request.FILES)
    if request.method == 'POST':
        with request.FILES['file'] as file:  # There should only be one file
            print(file)
            clean_name = str(file)
            try:
                clean_name = request.POST['full_path']
            except KeyError:
                pass
            with transaction.atomic():  # Atomic to ensure we upload to both data sources.
                start_time = datetime.now()
                print("Uploading to Azure")
                new_di_file = DIFile.objects.create(partner=partner, azure_file=file, clean_name=clean_name)
                print("Upload took {}".format(datetime.now() - start_time))
                start_time = datetime.now()
                print("Uploading to b2")
                new_di_file.b2_file = file
                new_di_file.save()
                print("Upload took {}".format(datetime.now() - start_time))

            parent_node = parent_node.follow_or_create_path(clean_name)
            for sibling in parent_node.get_children():
                if sibling.file is not None and sibling.file.clean_name.split('/')[-1] == clean_name.split('/')[-1]:
                    # If reuploading a file, we delete the old version (also removes it from the tree)
                    sibling.delete()
                    sibling.file.delete()
            new_downloadable = Downloadable.objects.create(parent=parent_node, file=new_di_file)
            new_downloadable.save()  # This also updates the parent node and ancestors updated_timestamp
            di.files.add(new_di_file)
            di.save()
            return HttpResponse(status=200)
    else:
        return HttpResponse(status=500)
    pass


def verify_user_can_edit(di_id, partner_slug, request):
    partner = get_partner_or_401(request, partner_slug)
    di = get_object_or_404(DigitalItem, id=di_id)

    if request.user not in di.partner.administrators.all():  # Only partner can upload files
        raise PermissionDenied
    return di, partner


@login_required
def remove_file(request, partner_slug, product_slug, di_id, di_file_id):
    verify_user_can_edit(di_id, partner_slug, request)

    try:
        di_file = get_object_or_404(DIFile, id=di_file_id)
        di_file.delete()
        return HttpResponse(status=200)
    except Exception as e:
        return HttpResponse(status=500)


@login_required
def remove_downloadable(request, partner_slug, product_slug, di_id, downloadable_id):
    verify_user_can_edit(di_id, partner_slug, request)

    try:
        downloadable = get_object_or_404(Downloadable, id=downloadable_id)
        downloadable.cascading_delete()
        return HttpResponse(status=200)
    except Exception as e:
        print(e)
        return HttpResponse(status=500)


@login_required
def upload_torrent(request, partner_slug, product_slug, di_id, di_file_id):
    partner = get_partner_or_401(request, partner_slug)
    di = get_object_or_404(DigitalItem, id=di_id)
    di_file = get_object_or_404(DIFile, id=di_file_id)

    print(request.POST)
    print(request.FILES)
    if request.method == 'POST':
        with request.FILES['torrent_file'] as file:  # There should only be one file
            print(file)
            di_file.torrent_file = file
            di_file.save()
            return HttpResponse(status=200)
    else:
        return HttpResponse(status=500)
    pass


def refresh_downloads(request, user_id):
    # stuff not in openCG&T
    return HttpResponse(status=200)
