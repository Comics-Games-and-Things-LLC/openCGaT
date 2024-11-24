from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse

from images.forms import EditAltText
from images.models import Image
from partner.models import get_partner_or_401
from shop.models import Product


def edit_alt_text(request, partner_slug, product_slug, image_id):
    partner = get_partner_or_401(request, partner_slug)
    product = get_object_or_404(Product, slug=product_slug)
    image = get_object_or_404(Image, id=image_id)
    form = EditAltText(instance=image)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EditAltText(request.POST, instance=image)
        # check whether it's valid:
        if form.is_valid():
            form.save()
            # redirect to a new URL:
            return HttpResponseRedirect(
                reverse("manage_product", kwargs={'partner_slug': partner.slug, 'product_slug': product.slug})
            )

    context = {
        'form': form,
        'image': image,
        'partner': partner,
    }
    return TemplateResponse(request, "images/edit_image_alt_text.html", context=context)
