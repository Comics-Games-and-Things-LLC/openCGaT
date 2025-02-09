import json
import traceback

from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from partner.models import Partner
from payments.models import PaypalPayment, StripePayment
from .forms import ShippingAddressForm
from .models import Cart


@csrf_exempt
def cart_freeze(request):
    if request.method == "POST":
        try:
            request.cart.freeze()
            request.cart.save()
            return HttpResponse(status=200)
        except Exception as e:
            print(e)
            return HttpResponse(status=400)
    return HttpResponse(400)


@csrf_exempt
def cart_thaw(request):
    if request.method == "POST":
        try:
            request.cart.thaw()
            request.cart.save()
            return HttpResponse(status=200)
        except Exception as e:
            print(e)
            return HttpResponse(status=400)
    return HttpResponse(400)


@csrf_exempt
def cart_set_email(request):
    if request.method == "POST":
        try:
            cart = request.cart
            body = json.loads(request.body.decode('utf-8'))
            cart.email = body['email']
            cart.save()
            if cart.discount_code:
                cart.discount_code.validate_code_for_cart(cart)
                cart.save()
            return HttpResponse(status=200)
        except Exception as e:
            print(e)
            return HttpResponse(status=400)
    return HttpResponse(400)


@csrf_exempt
def cart_set_shipping_address(request):
    cart = request.cart
    if request.method == "POST":
        try:
            form = ShippingAddressForm(data=request.POST, instance=request.cart.shipping_address)
            if form.is_valid():
                request.cart.shipping_address = form.save()
                request.cart.tax_error = False
                request.cart.address_error = None
                request.cart.delivery_method = Cart.SHIP_ALL
                request.cart.pickup_partner = None
                request.cart.update_final_totals()
                request.cart.save()
            else:
                request.cart.address_error = form.errors.as_json()
                request.cart.save()
            return HttpResponse(status=200)
        except Exception as e:
            print(e)
            return HttpResponse(status=400)
    return HttpResponse(400)


@csrf_exempt
def cart_set_pickup_partner(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body.decode('utf-8'))
            slug = body['partner_slug']
            request.cart.pickup_partner = Partner.objects.get(slug=slug)
            request.cart.delivery_method = Cart.PICKUP_ALL
            request.cart.update_final_totals()
            request.cart.save()
            return HttpResponse(status=200)
        except Exception as e:
            print(e)
            return HttpResponse(status=400)
    return HttpResponse(400)


@csrf_exempt
def create_paypal_payment(request):
    if not request.cart.is_frozen:
        return HttpResponse(403)
    request.cart.final_ship = request.cart.get_shipping()
    request.cart.final_tax = request.cart.get_tax(final=True)
    request.cart.final_total = request.cart.get_final_less_tax() + request.cart.final_tax
    request.cart.save()
    if request.method == 'POST':
        try:
            payment, created = PaypalPayment.objects.get_or_create(cart=request.cart,
                                                                   requested_payment=request.cart.final_total)
            return JsonResponse(payment.get_or_make_order())
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            return HttpResponse(status=500)
    return HttpResponse(status=500)


@csrf_exempt
def capture_paypal_payment(request, order_id):
    try:
        payment = PaypalPayment.objects.get(cart=request.cart, order_id=order_id)
        return JsonResponse(payment.check_status_and_mark_paid())
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return HttpResponse(status=500)


@csrf_exempt
def pay_at_pickup_location(request):
    if not request.cart.is_frozen:
        return HttpResponse(status=403)
    if request.cart.pickup_partner:
        request.cart.payment_partner = request.cart.pickup_partner
        request.cart.payment_method = request.cart.PAY_IN_STORE
        request.cart.save()
        # Need to save pay in store before submitting the order as the submit email will reload the object from the db.
        request.cart.submit()
        request.cart.save()
        return HttpResponse(status=200)
    return HttpResponse(status=403)


@csrf_exempt
def mark_free_as_paid(request):
    if not request.cart.is_frozen:
        return HttpResponse(status=403)
    if request.cart.is_free():
        request.cart.pay()
        request.cart.save()
        return HttpResponse(status=200)
    return HttpResponse(status=403)


@csrf_exempt
def create_stripe_payment(request):
    print(request.cart)
    print(request.cart.is_frozen)
    if not request.cart.is_frozen:
        return HttpResponse(403)
    request.cart.final_ship = request.cart.get_shipping()
    request.cart.final_tax = request.cart.get_tax(final=True)
    request.cart.final_total = request.cart.get_final_less_tax() + request.cart.final_tax
    request.cart.save()
    if request.method == 'POST':
        try:
            payment_intent = StripePayment.get_create_or_update_intent_for_cart(request.cart)
            return JsonResponse(payment_intent.get_client_secret())
        except Exception as e:
            print(e)
            print(traceback.format_exc())
            return HttpResponse(status=500)
    return HttpResponse(status=500)


@csrf_exempt
def confirm_stripe_capture(request):
    intent_id = request.GET.get("payment_intent")
    payment = StripePayment.objects.get(intent_id=intent_id)
    cart = payment.cart
    cart.mark_processing()
    try:
        payment.check_payment()
    except Exception as e:
        print(e)
        print(traceback.format_exc())
    return HttpResponseRedirect(reverse("checkout_complete", kwargs={"order_id": cart.id}))


@csrf_exempt
def payment_api_info(request):
    """
    Returns the Stripe publishable key and PayPal client ID
    :param request:
    :return: STRIPE_PUBLIC_KEY and PAYPAL_CLIENT_ID as JSON
    """

    return JsonResponse({"STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
                         "PAYPAL_CLIENT_ID": settings.PAYPAL_CLIENT_ID,
                         })
