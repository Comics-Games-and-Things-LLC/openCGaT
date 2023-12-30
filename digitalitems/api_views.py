from allauth.account.decorators import verified_email_required
from django.contrib.postgres.search import SearchQuery
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from digitalitems.forms import FiltersForm
from digitalitems.models import DigitalItem
from digitalitems.serializers import DownloadableSerializer, DigitalItemSerializer


@verified_email_required
def account_downloads_v2(request, refresh=0):
    page_size = 10
    site_partner = None
    initial_data = {'page_size': page_size}
    if request.user.is_authenticated:
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
        entry_num = 0
        for di in page:
            data = {
                'info': DigitalItemSerializer(di, context={'user': request.user}).data
            }
            if di.root_downloadable:
                data["root_folder"] = {}
                data['root_folder']['downloadable'] = DownloadableSerializer(di.root_downloadable,
                                                                             context={'user': request.user}).data
            else:
                data['root_folder'] = None
            download_list[entry_num] = data
            entry_num += 1
        context = {
            'download_list': download_list,
            "purchased": True,
            'filters_form': form,
            'page': page,
            'page_number': page_number,
            'manual_form_fields': []
        }
        return TemplateResponse(request, "digital/downloadsv2.html", context=context)

    else:
        return redirect("account_login")
