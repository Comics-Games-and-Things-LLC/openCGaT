from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from inventory_report.models import InventoryReport, InventoryReportLocation, InventoryReportLine
from partner.models import get_partner_or_401
from shop.models import InventoryItem, Product


@login_required
def index(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    context = {
        'partner': partner,
        'reports': InventoryReport.objects.filter(partner=partner).order_by("-date"),
    }
    return render(request, "inventory_report/index.html", context)


@login_required
def report_details(request, partner_slug, report_id, location_id=None):
    partner = get_partner_or_401(request, partner_slug)
    report = InventoryReport.objects.get(id=report_id, partner=partner)
    location = None
    locations = None
    lines = report.report_lines.order_by('-timestamp')
    if location_id:
        location = InventoryReportLocation.objects.get(id=location_id, partner=partner)
        lines = lines.filter(location=location)
    else:
        locations = InventoryReportLocation.objects.filter(partner=partner)
    context = {
        'partner': partner,
        'location': location,
        'locations': locations,
        'report': report,
        'lines': lines
    }
    return render(request, "inventory_report/report.html", context)


@login_required
def add(request, partner_slug, report_id, location_id=None, barcode=None):
    partner = get_partner_or_401(request, partner_slug)
    report = InventoryReport.objects.get(id=report_id, partner=partner)
    location = None
    data = {}

    if location_id:
        location = InventoryReportLocation.objects.get(id=location_id)
    if barcode:
        InventoryReportLine.objects.create(report=report, location=location, barcode=barcode)
        data['success'] = True

    potential_product = Product.objects.filter(barcode=barcode)
    if potential_product.exists():
        product = potential_product.first()
        data["product"] = {
            "slug": product.slug,
            "name": product.name
        }
        potential_item = InventoryItem.objects.filter(product=product)
        if potential_item.exists():
            item = potential_item.first()
            data["item"] = {
                "id": item.id,
                "count": item.current_inventory
            }

    return JsonResponse(data=data)


def delete_inv_report_line(request, partner_slug, report_id, report_line_id, confirm=0, location_id=None):
    partner = get_partner_or_401(request, partner_slug)
    line = get_object_or_404(InventoryReportLine, id=report_line_id, report__partner=partner)
    kwargs = {'partner_slug': partner.slug,
              'report_id': report_id,
              }
    if location_id:
        kwargs['location_id'] = location_id

    next_url = reverse("report", kwargs=kwargs)

    if int(confirm) == 1:
        line.delete()
        return HttpResponseRedirect(next_url)
    kwargs['confirm'] = 1
    kwargs['report_line_id'] = report_line_id
    context = {
        'item_name': "{}".format(line),
        'confirm_url': reverse('delete_inv_report_line', kwargs=kwargs),
        'back_url': next_url,
    }
    return render(request, "confirm_delete.html", context=context)
