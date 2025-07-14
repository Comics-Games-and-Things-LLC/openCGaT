from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse

from dist_requests.forms import DistRequestLineForm
from partner.models import get_partner_or_401
from shop.models import Product


# Create your views here.
def log_dist_request(request, partner_slug, product_slug):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = DistRequestLineForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            form.save(partner=partner, product=product)
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("manage_product", kwargs={'partner_slug': partner.slug,
                                                                          'product_slug': product_slug}))
    context = {
        'form': DistRequestLineForm(),
        'partner': partner
    }
    return TemplateResponse(request, "create_from_form.html", context=context)