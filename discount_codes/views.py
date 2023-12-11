from decimal import Decimal

from django.db.models import Sum, F
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from djmoney.money import Money

from checkout.models import CheckoutLine, Cart
from discount_codes.models import DiscountCode, CodeUsage, Referrer
from partner.models import get_partner_or_401


# Create your views here.

@csrf_exempt
def apply_code(request, code: str = "", cart=None):
    potential_codes = DiscountCode.objects.filter(code=code.lower())

    if cart is None:
        cart = request.cart

    if code.strip() == "":
        cart.discount_code_message = None
        cart.discount_code = None
        cart.save()  # Clear code if none is given
        return HttpResponse(status=200)

    if potential_codes.exists():
        next_page = request.GET.get("next")

        code = potential_codes.first()
        user = None
        if request.user.is_authenticated:
            user = request.user
        CodeUsage.objects.create(code=code, cart_id=cart.id, user=user)
        if code.validate_code_for_cart(cart):
            pass  # Validating the code saves it to the cart.
        else:
            next_page = reverse('view_cart')  # redirect user to page where they can see error message

        if request.method == "POST":
            return HttpResponse(status=200)
        if next_page is None:
            next_page = reverse('shop')
        return HttpResponseRedirect(next_page)
    else:
        cart.discount_code_message = f"The code '{code}' does not exist"
    cart.discount_code = None
    cart.save()  # Clear code if we can't find the discount.
    return HttpResponse(status=200)


def referral_index(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    referrers = Referrer.objects.all()
    context = {"partner": partner,
               "referrers": referrers}

    return render(request, "discount_codes/referrer_index.html", context)


def referral_report(request, partner_slug, referrer_slug):
    partner = get_partner_or_401(request, partner_slug)
    referrer = get_object_or_404(Referrer, slug=referrer_slug)
    codes = DiscountCode.objects.filter(referrer=referrer, partner_discounts__partner=partner)

    kickback_earnings = Money(0, "USD")
    sales_total = Money(0, "USD")

    code_details = {}
    for code in codes:
        code_details[code] = {}

        kickback_percentage = Decimal(code.partner_discounts.get(partner=partner).referrer_kickback / 100)
        sales_amount = CheckoutLine.objects.exclude(cart__status=Cart.CANCELLED, cancelled=True).filter(
            cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED], cart__discount_code=code).order_by(
            "cart__date_paid").aggregate(sum=Sum(F('price_per_unit_at_submit') * F('quantity')))["sum"]

        if sales_amount:
            kickback_amount = Money(sales_amount * kickback_percentage, "USD")
            kickback_earnings += kickback_amount
            code_details[code]["kickback"] = kickback_amount
            sales_total += Money(sales_amount, "USD")
            code_details[code]["sales"] = sales_total

            code_details[code]["cart_count"] = Cart.submitted.filter(discount_code=code).count()
            code_details[code]["click_count"] = CodeUsage.objects.filter(code=code).count()

    context = {"partner": partner,
               "referrer": referrer,
               "kickback_earnings": kickback_earnings,
               "codes": codes,
               "code_details": code_details,
               }

    return render(request, "discount_codes/referrer_summary.html", context)


def referral_code_report(request, partner_slug, referrer_slug, code):
    partner = get_partner_or_401(request, partner_slug)
    referrer = get_object_or_404(Referrer, slug=referrer_slug)
    code = get_object_or_404(DiscountCode, referrer=referrer, partner_discounts__partner=partner, code=code)

    kickback_earnings = Money(0, "USD")

    kickback_lines = {}  # Cart: {earnings: Money, items: str}
    kickback_percentage = Decimal(code.partner_discounts.get(partner=partner).referrer_kickback / 100)
    referred_lines = CheckoutLine.objects.exclude(cart__status=Cart.CANCELLED, cancelled=True).filter(
        cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED], cart__discount_code=code).order_by(
        "cart__date_paid")
    for line in referred_lines:
        print(line)
        earnings_this_line = line.price_per_unit_at_submit * line.quantity * kickback_percentage
        kickback_earnings += earnings_this_line
        if line.cart not in kickback_lines:
            kickback_lines[line.cart] = {"kickback": earnings_this_line, "items": [line.item.product.name]}
        else:
            kickback_lines[line.cart]["kickback"] += earnings_this_line
            kickback_lines[line.cart]["items"].append(line.item.product.name)
    context = {"partner": partner,
               "referrer": referrer,
               "code": code,
               "kickback_earnings": kickback_earnings,
               "kickback_lines": kickback_lines,
               }

    return render(request, "discount_codes/referrer_code_report.html", context)
