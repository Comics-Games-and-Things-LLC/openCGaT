import datetime

from django.db.models import Sum, F
from django.shortcuts import render

from checkout.models import Cart
from intake.models import PurchaseOrder
# Create your views here.
from partner.models import get_partner_or_401


def sales_overview(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    carts = Cart.submitted.exclude(status__in=['Cancelled', 'Submitted']).exclude(date_paid=None)
    year = datetime.date.today().year
    POs = PurchaseOrder.objects.filter(date__year__gte=year)
    print(POs.aggregate(Sum('amount_charged'))['amount_charged__sum'])
    print(carts.annotate(net=(F('final_total') - F('final_tax'))).aggregate(Sum('net'))['net__sum'])
    print(carts.annotate(net=(F('final_total') - F('final_tax'))).aggregate(Sum('net'))['net__sum'])

    gross_by_day = carts.values('date_paid__date').order_by('-date_paid__date').annotate(gross=Sum('final_total'),
                                                                                         post_tax=Sum(F('final_total') - F(
                                                                                             'final_tax')))

    context = {
        "gross_by_day": gross_by_day
    }
    return render(request, "partner_sales_overview.html", context)
