import json
from _decimal import Decimal

import stripe
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from djmoney.money import Money

import discount_codes.views
from digitalitems.models import DigitalItem
from partner.models import get_partner_or_401
from shop.models import CustomChargeItem, Product, Item, InventoryItem
from shop.serializers import ItemSerializer
from .forms import PickupForm, EmailForm, BillingAddressForm, PaymentMethodForm, ShippingAddressForm, FiltersForm, \
    TrackingInfoForm, PartnerCommentsForm
from .models import Cart, CheckoutLine, StripeCustomerId, StripePaymentIntent
from .serializers import CartSerializer, get_pos_props


@csrf_exempt
def json_cart(request):
    response = {}
    if request.cart.id is not None:
        response = CartSerializer(request.cart).data
    response['buttonItems'] = []
    if request.method == 'POST':
        data = json.loads(request.body)
        try:
            item_ids = data['buttonItems']
            for item in Item.objects.filter(id__in=item_ids):
                response['buttonItems'].append(ItemSerializer(item, context={'cart': request.cart}).data)
        except KeyError:
            pass
    return JsonResponse(response)


@csrf_exempt
def add_to_cart(request, item_id, quantity=1):
    try:
        item = get_object_or_404(Item, id=item_id)
        line, _ = request.cart.add_item(item, quantity)
        if isinstance(item, DigitalItem) \
                and item.pay_what_you_want and request.method == 'POST':
            print(request.body)
            body = json.loads(request.body)
            user_price = Money(Decimal(body['price']), "USD")
            if user_price >= item.price:
                try:
                    line.price_per_unit_override = user_price
                    print("Saved item at pwyw price!")
                    line.save()
                except KeyError:
                    pass
        return HttpResponse(status=200)
    except Exception as e:
        print(e)
    return HttpResponse(status=400)


def remove_from_cart(request, item_id):
    try:
        request.cart.remove_from_cart(item_id)
        return HttpResponse(status=200)
    except Exception as e:
        print(e)
    return HttpResponse(status=400)


def update_quantity(request, item_id, quantity):
    try:
        request.cart.update_quantity(item_id=item_id, quantity=quantity)
        return HttpResponse(status=200)
    except Exception as e:
        return HttpResponse(status=400)


def view_cart(request):
    return TemplateResponse(request, "checkout/view_cart.html")


def checkout_start(request):
    request.cart.freeze()
    context = {
        'next_view': request.cart.next_checkout_view(view=Cart.V_START, user=request.user),
    }
    return TemplateResponse(request, "checkout/checkout_start.html", context=context)


def checkout_react(request):
    context = {
        'props': {},
    }
    return TemplateResponse(request, "checkout/react_checkout.html", context=context)


def checkout_delivery_method(request):
    '''
    This view allows the user to select a delivery method (in store pickup or shipping)
    and if in-store, which store to pick up from.
    :param request:
    :return:
    '''
    if not request.cart.is_frozen:
        return HttpResponseRedirect(reverse('checkout_start'))
    if not request.cart.is_account_set():
        return HttpResponseRedirect(reverse('checkout_login'))

    form = PickupForm(instance=request.cart)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = PickupForm(request.POST, instance=request.cart)

        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            form.save()
            # redirect to a new URL:
            next_view = request.cart.next_checkout_view(view=Cart.V_DELIVERY_METHOD, user=request.user)

            return HttpResponseRedirect(reverse(next_view))

    context = {
        'form': form,
    }
    return TemplateResponse(request, "checkout/checkout_pickup_in_store.html", context=context)


def checkout_login(request):
    if not request.cart.is_frozen:
        return HttpResponseRedirect(reverse('checkout_start'))
    form = EmailForm(instance=request.cart)
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EmailForm(request.POST, instance=request.cart)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            form.save()
            cart = request.cart
            code = cart.discount_code
            if code:
                code.validate_code_for_cart(cart)
            # redirect to a new URL:
            next_view = request.cart.next_checkout_view(view=Cart.V_LOGIN, user=request.user)

            return HttpResponseRedirect(reverse(next_view))

    context = {
        'form': form,
    }
    return TemplateResponse(request, "checkout/checkout_login.html", context=context)


def checkout_billing_addr(request):
    if not request.cart.is_frozen:
        return HttpResponseRedirect(reverse('checkout_start'))
    if not request.cart.is_account_set():
        return HttpResponseRedirect(reverse('checkout_login'))
    if not request.cart.is_shipping_set():
        return HttpResponseRedirect(reverse(Cart.V_DELIVERY_METHOD))

    billing_form = BillingAddressForm(instance=request.cart.billing_address)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        billing_form = BillingAddressForm(data=request.POST, instance=request.cart.billing_address)

        # check whether it's valid:
        if billing_form.is_valid():
            # process the data in form.cleaned_data as required
            request.cart.billing_address = billing_form.save()
            request.cart.tax_error = False
            request.cart.save()
            # redirect to a new URL:
            next_view = request.cart.next_checkout_view(view=Cart.V_BILLING_ADDRESS, user=request.user)

            return HttpResponseRedirect(reverse(next_view))

    context = {
        'billing_form': billing_form,
    }
    return TemplateResponse(request, "checkout/checkout_billing_addr.html", context=context)


def checkout_payment_method(request):
    '''
    This form asks the users for their payment method, and the store to pay in.
    :param request:
    :return: redirects to done
    '''
    if not request.cart.is_frozen:
        return HttpResponseRedirect(reverse('checkout_start'))
    if not request.cart.is_account_set():
        return HttpResponseRedirect(reverse('checkout_login'))
    if not request.cart.is_shipping_set():
        return HttpResponseRedirect(reverse(Cart.V_DELIVERY_METHOD))

    payment_form = PaymentMethodForm(instance=request.cart)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        payment_form = PaymentMethodForm(request.POST, instance=request.cart)

        # check whether it's valid:
        if payment_form.is_valid():
            # process the data in form.cleaned_data as required
            payment_form.save()
            # redirect to a new URL:
            next_view = request.cart.next_checkout_view(view=Cart.V_PAYMENT_METHOD, user=request.user)
            return HttpResponseRedirect(reverse(next_view))

    context = {
        'payment_form': payment_form,
    }
    return TemplateResponse(request, "checkout/checkout_payment_method.html", context=context)


def checkout_pay_online(request):
    '''
    This form allows the user to pay online via credit card
    :param request:
    :return:
    '''

    if not request.cart.is_frozen:
        return HttpResponseRedirect(reverse(Cart.V_START))
    if not request.cart.is_account_set():
        return HttpResponseRedirect(reverse(Cart.V_LOGIN))
    if not request.cart.is_shipping_set():
        return HttpResponseRedirect(reverse(Cart.V_DELIVERY_METHOD))
    if not request.cart.is_payment_method_set():
        return HttpResponseRedirect(reverse(Cart.V_PAYMENT_METHOD))
    if not request.cart.can_get_tax():
        return HttpResponseRedirect(reverse(Cart.V_BILLING_ADDRESS))

    request.cart.final_ship = request.cart.get_shipping()
    request.cart.final_tax = request.cart.get_tax(final=True)
    request.cart.final_total = request.cart.get_final_less_tax() + request.cart.final_tax
    request.cart.save()

    context = {
        'final_tax': request.cart.final_tax,
        'final_total': request.cart.final_total,
    }
    return TemplateResponse(request, "checkout/checkout_pay_online.html", context=context)


def checkout_shipping_address(request):
    '''
    This form asks the user their shipping address.
    :param request:
    :return:
    '''
    if not request.cart.is_frozen:
        return HttpResponseRedirect(reverse('checkout_start'))
    if not request.cart.is_account_set():
        return HttpResponseRedirect(reverse('checkout_login'))
    form = ShippingAddressForm(instance=request.cart.shipping_address)

    if request.method == 'POST':
        print(request.POST)
        # create a form instance and populate it with data from the request:
        form = ShippingAddressForm(data=request.POST, instance=request.cart.shipping_address)
        print(form.is_bound)
        # check whether it's valid:
        if form.is_valid():
            print("Form valid")
            # process the data in form.cleaned_data as required
            request.cart.shipping_address = form.save()
            request.cart.tax_error = False
            request.cart.save()
            # redirect to a new URL:
            next_view = request.cart.next_checkout_view(view=Cart.V_SHIPPING_ADDR, user=request.user)

            return HttpResponseRedirect(reverse(next_view))
        else:
            print("Form invalid")
            for field in form:
                print("Field Error:", field.name, field.errors)
            print(form.errors)

    context = {
        'form': form,
    }
    return TemplateResponse(request, "checkout/checkout_delivery.html", context=context)


def checkout_done(request):
    print(request.cart)
    if not request.cart.is_frozen:
        return HttpResponseRedirect(reverse(Cart.V_START))
    if not request.cart.is_account_set():
        return HttpResponseRedirect(reverse(Cart.V_LOGIN))
    if not request.cart.is_shipping_set():
        return HttpResponseRedirect(reverse(Cart.V_DELIVERY_METHOD))
    if not request.cart.is_payment_set():
        return HttpResponseRedirect(reverse(Cart.V_PAYMENT_METHOD))
    if not request.cart.is_billing_addr_required() and request.cart.billing_address:
        return HttpResponseRedirect(reverse(Cart.V_BILLING_ADDRESS))

    request.cart.submit()
    print(request.cart)
    context = {'order_id': request.cart.id}
    return TemplateResponse(request, "checkout/checkout_done.html", context=context)


def checkout_complete(request, order_id):
    """
    Landing page for checkout 2.0 complete
    :param request:
    :param order_id:
    :return:
    """
    old_cart = Cart.objects.get(id=order_id)

    context = {'order': old_cart}
    return TemplateResponse(request, "checkout/checkout_done.html", context=context)


@login_required
def past_orders(request):
    orders = Cart.submitted.filter(owner=request.user).order_by('date_submitted')
    context = {'past_orders': orders,
               'other_items_for_customer': CheckoutLine.objects.filter(cart__owner=request.user,
                                                                       fulfilled=False,
                                                                       cancelled=False,
                                                                       ).exclude(cart__status__in=[Cart.COMPLETED,
                                                                                                   Cart.CANCELLED]
                                                                                 ).order_by('-cart__date_submitted')}
    return TemplateResponse(request, "checkout/past_orders.html", context=context)


def past_order_details(request, cart_id):
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        if past_cart.owner and past_cart.owner != request.user and not request.user.is_staff:
            return HttpResponse(status=403)
        context = {'past_cart': past_cart}
        return TemplateResponse(request, "checkout/order_details.html", context=context)
    except Cart.DoesNotExist:
        return HttpResponse(status=404)


@require_POST
@csrf_exempt
def stripe_webhook(request):
    return HttpResponse(status=200)

    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_ENDPOINT_SECRET
        )
    except ValueError as e:
        # Invalid payload
        print(e)
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print(e)
        return HttpResponse(status=400)

    # Handle the event
    print(event.type)
    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object  # contains a stripe.PaymentIntent
        payment_intent_object = StripePaymentIntent.objects.get(id=payment_intent.id)
        payment_intent_object.try_mark_captured()
        print('PaymentIntent was successful!')

    elif event.type == 'payment_method.attached':
        payment_method = event.data.object  # contains a stripe.PaymentMethod
        print('PaymentMethod was attached to a Customer!')
    # ... handle other event types
    elif event.type == 'charge.succeeded':
        payment_intent_id = event.data.object.payment_intent  # contains a stripe.PaymentIntent
        charge = event.data.object  # contains a stripe.Charge
        payment_intent_object = StripePaymentIntent.objects.get(id=payment_intent_id)
        payment_intent_object.try_mark_captured()
    else:
        # Unexpected event type
        return HttpResponse(status=400)

    return HttpResponse(status=200)


@login_required
def partner_orders(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug=partner_slug)

    lines = CheckoutLine.objects.filter(partner_at_time_of_submit=partner)
    orders = Cart.submitted.filter(lines__in=lines) \
             | Cart.submitted.filter(payment_partner=partner, payment_method=Cart.PAY_IN_STORE) \
             | Cart.submitted.filter(pickup_partner=partner, delivery_method=Cart.PICKUP_ALL)
    orders = orders.distinct()

    form = FiltersForm()

    # https://medium.com/apollo-data-solutions-blog/django-initial-values-for-a-bound-form-fde7b363f79e
    if request.method == 'GET':
        if len(request.GET):  # If there's actually data, use that data.
            form = FiltersForm(request.GET)
        orders = form.get_orders(orders)

    orders = orders.order_by('-date_submitted')
    paginator = Paginator(orders, 10)
    page_number = int(request.GET.get('page_number', 1))
    page = paginator.get_page(page_number)

    context = {
        'page': page,
        'filters_form': form,
        'page_number': int(page_number),
        'partner': partner,
    }
    return TemplateResponse(request, "checkout/partner_orders.html", context=context)


@login_required
def partner_order_details(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        form = TrackingInfoForm(instance=past_cart)

        context = {'past_cart': past_cart, 'partner': partner, 'form': form}

        if request.method == 'POST':
            # create a form instance and populate it with data from the request:
            form = TrackingInfoForm(request.POST, instance=past_cart)

            # check whether it's valid:
            if form.is_valid():
                # process the data in form.cleaned_data as required
                past_cart = form.save()
                past_cart.mark_shipped()
                print(past_cart)
        context['comments_form'] = PartnerCommentsForm(instance=past_cart)
        if past_cart.owner:
            context['other_items_for_customer'] = CheckoutLine.objects.filter(cart__owner=past_cart.owner,
                                                                              cart__status=Cart.PAID,
                                                                              fulfilled=False
                                                                              ).exclude(
                cart__id=past_cart.id
            )

        return TemplateResponse(request, "checkout/partner_order_details.html", context=context)
    except Cart.DoesNotExist:
        return HttpResponse(status=404)


@login_required
def partner_order_printout(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        past_cart.invoice_been_printed = True
        past_cart.save()
        context = {'past_cart': past_cart, 'partner': partner}
        return TemplateResponse(request, "checkout/partner_order_printout.html", context=context)
    except Cart.DoesNotExist:
        return HttpResponse(status=404)


@login_required
def partner_order_mark_paid(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        if past_cart.payment_partner.id is not partner.id:
            return HttpResponse(status=403)
        past_cart.pay()
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Cart.DoesNotExist:
        return HttpResponse(status=404)


@login_required
def partner_order_mark_completed(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        if past_cart.pickup_partner.id != partner.id:
            return HttpResponse(status=403)
        past_cart.mark_completed()
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Cart.DoesNotExist:
        return HttpResponse(status=404)


@login_required
def partner_order_ready_for_pickup(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        if past_cart.pickup_partner.id != partner.id:
            return HttpResponse(status=403)
        past_cart.mark_ready_for_pickup()
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Cart.DoesNotExist:
        return HttpResponse(status=404)


@login_required
def past_order_mark_cancelled(request, cart_id, partner_slug=None):
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        if partner_slug:
            get_partner_or_401(request, partner_slug=partner_slug)
        elif request.user != past_cart.owner:
            return HttpResponse(status=403)
        past_cart.cancel()
        if partner_slug:
            return HttpResponseRedirect(
                reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
        else:
            return HttpResponseRedirect(
                reverse('past_order_details', kwargs={'cart_id': cart_id}))

    except Cart.DoesNotExist:
        return HttpResponse(status=404)


@login_required
def saved_cards(request):
    cards = None
    customer = None
    if hasattr(request.user, 'stripe_id'):
        pass
    else:
        StripeCustomerId.objects.create(user=customer, id=stripe.Customer.create())

    cards = stripe.PaymentMethod.list(
        customer=request.user.stripe_id.id,
        type="card",
    )
    intent = stripe.SetupIntent.create(
        customer=request.user.stripe_id.id,
    )
    context = {
        'cards': cards,
        'intent': intent,
        'publishableAPIKey': settings.STRIPE_PUBLIC_KEY,

    }

    return TemplateResponse(request, "account/saved_cards.html", context=context)


@login_required
def remove_card(request, card_id):
    if hasattr(request.user, 'stripe_id'):
        cards = stripe.PaymentMethod.list(
            customer=request.user.stripe_id.id,
            type="card",
        )
        for card in cards.data:
            if card.id == card_id:
                stripe.PaymentMethod.detach(
                    card_id
                )

    return HttpResponseRedirect(reverse('saved_cards'))


def pos(request, partner_slug, cart_id=None):
    partner = get_partner_or_401(request, partner_slug)
    context = {
        'partner': partner,
        'props': get_pos_props(partner, cart_id),
    }
    return TemplateResponse(request, "checkout/pos.html", context=context)


def pos_create_cart(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.create(at_pos=True, payment_partner=partner, payment_method=Cart.PAY_IN_STORE,
                               pickup_partner=partner, delivery_method=Cart.PICKUP_ALL, site=partner.site)

    return JsonResponse({'id': cart.id})


def pos_add_item(request, partner_slug, cart_id, barcode):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    if cart.is_paid or cart.is_cancelled:
        return HttpResponseNotFound
    product = Product.objects.get(barcode=barcode)

    items = InventoryItem.objects.filter(product=product)
    if partner:
        items = items.filter(partner=partner)
    items = items.order_by('price')
    in_stock = items.filter(current_inventory__gt=0)
    if in_stock.exists():
        cart.add_item(in_stock.first())
    else:
        cart.add_item(items.last())

    return HttpResponse(status=200)


def pos_suggest_owner(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug)
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        email = body['email']
        print(email)
        if email.strip() == "":
            return JsonResponse({'users': []})
        users = User.objects.filter(emailaddress__email__icontains=email).distinct()
        users = users | User.objects.filter(username__icontains=email).distinct()
        users = users.distinct()
        print(users)
        serialized_users = []
        for user in users[:5]:
            serialized_users.append({
                "username": user.username,
                "email": user.email,
            })
        return JsonResponse({'users': serialized_users})
    return HttpResponse(status=400)


def pos_set_owner(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        email = body['email']
        print(email)
        if " " in email:
            return HttpResponse(status=400)
        try:
            user = User.objects.get(emailaddress__email=email)
            cart.owner = user
            print("Set Owner")
        except Exception:

            cart.email = email
            print("Set Email instead of owner")

        cart.save()
        return HttpResponse(status=200)
    return HttpResponse(status=400)


def pos_set_code(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        code = body['code']
        print(code)
        if " " in code:
            return HttpResponse(status=200)
        return discount_codes.views.apply_code(request, code, cart)
    return HttpResponse(status=400)


def pos_add_custom(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug)
    cart = get_object_or_404(Cart, id=cart_id)
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        product, _ = Product.objects.get_or_create(name="Custom Item or Service")
        price = Money(body['price'], 'USD')
        custom_charge_item = CustomChargeItem.objects.create(partner=partner, product=product,
                                                             price=price, default_price=price,
                                                             description=body['description'])
        custom_charge_item.save()

        # Add item to  cart
        cart.add_item(custom_charge_item)
        return HttpResponse(status=200)
    return HttpResponse(status=400)


def pos_pay_cash(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    if cart.payment_partner != partner:
        return HttpResponse(403)

    if cart.status != cart.SUBMITTED:
        cart.submit()
    amount = cart.final_total.amount
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        amount = body['amount']

    print(amount)
    if amount is not None:
        cart.pay_amount(amount, cash=True)
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=400)


def pos_create_stripe_payment(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)

    if cart.payment_partner != partner:
        return HttpResponse(status=403)

    if cart.status != cart.SUBMITTED:
        cart.submit()

    customer_id = None
    if cart.owner:
        customer_id = StripeCustomerId.objects.get_customer_id(user=cart.owner)

    amount = cart.final_total.amount
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        print(body)
        amount = body['amount']

    intent = stripe.PaymentIntent.create(
        customer=customer_id,
        payment_method_types=['card_present'],
        capture_method='manual',
        amount=int(amount * 100),
        currency='usd',
        description=f"Cart Number {cart.id}",
    )

    cart.stripepaymentintent_set.create(id=intent.stripe_id, amount_to_pay=amount)
    return JsonResponse({
        'client_secret': intent['client_secret'],
        'publishableAPIKey': settings.STRIPE_PUBLIC_KEY,
    })


def stripe_terminal_connection_token(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    connection_token = stripe.terminal.ConnectionToken.create()
    return JsonResponse({
        'secret': connection_token.secret
    })


def stripe_capture(request, partner_slug, cart_id=None):
    partner = get_partner_or_401(request, partner_slug)
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        intent = stripe.PaymentIntent.capture(
            body['id']
        )
        print("Payment intent received")
        payment_intent_object = StripePaymentIntent.objects.get(id=intent.id)
        payment_intent_object.try_mark_captured()
        return JsonResponse({'intent': intent})
    return HttpResponse(status=400)


def partner_cart_endpoint(request, partner_slug, cart_id=None):
    partner = get_partner_or_401(request, partner_slug)
    return JsonResponse(get_pos_props(partner, cart_id))


def partner_update_quantity(request, cart_id, partner_slug, item_id, quantity):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    if cart.is_submitted:
        return HttpResponse(status=400)
    try:
        cart.update_quantity(item_id=item_id, quantity=quantity)
        return HttpResponse(status=200)
    except Exception as e:
        return HttpResponse(status=400)


def partner_update_line(request, cart_id, partner_slug, item_id):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    if request.method == "POST":
        print('post')
        try:
            line = cart.lines.get(item_id=item_id)
            body = json.loads(request.body.decode('utf-8'))
            print(body)

            try:
                line.quantity = body['quantity']
                print("Updating quantity")
            except KeyError:
                pass
            try:
                line.price_per_unit_override = Money(Decimal(body['price']), "USD")
                print("Updating price")
            except KeyError:
                pass
            line.save()
            return HttpResponse(status=200)
        except Exception as e:
            print(e)
            return HttpResponse(status=400)
    return HttpResponse(status=400)


def partner_remove_line(request, cart_id, partner_slug, item_id):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    if cart.is_submitted:
        return HttpResponse(status=400)
    try:
        cart.remove_from_cart(item_id)
        return HttpResponse(status=200)
    except Exception as e:
        print(e)
    return HttpResponse(status=400)


@staff_member_required
def all_orders_tax(request):
    orders = Cart.submitted.all()

    form = FiltersForm()

    # https://medium.com/apollo-data-solutions-blog/django-initial-values-for-a-bound-form-fde7b363f79e
    if request.method == 'GET':
        if len(request.GET):  # If there's actually data, use that data.
            form = FiltersForm(request.GET)
        orders = form.get_orders()

    orders = orders.order_by('-date_submitted').reverse()
    paginator = Paginator(orders, 10)
    page_number = int(request.GET.get('page_number', 1))
    page = paginator.get_page(page_number)

    context = {
        'page': page,
        'filters_form': form,
        'page_number': int(page_number),
    }
    return TemplateResponse(request, "all_orders_tax.html", context=context)


def partner_cancel_line(request, cart_id, line_id, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    try:
        line = cart.lines.get(id=line_id)
        if partner != line.partner_at_time_of_submit:
            return HttpResponse(status=401)
        line.cancel()
        line.save()
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Exception as e:
        print(e)
        return HttpResponse(status=400)


def partner_ready_line(request, cart_id, line_id, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    try:
        line = cart.lines.get(id=line_id)
        if partner != line.partner_at_time_of_submit:
            return HttpResponse(status=401)
        line.mark_ready()
        line.save()
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Exception as e:
        print(e)
        return HttpResponse(status=400)


def partner_complete_line(request, cart_id, line_id, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    # Cart is the cart page that's open, will be used as the fulfilment cart unless there's a get param.
    # Cart is not necessarily this item's cart.`
    try:
        line = CheckoutLine.objects.get(id=line_id)
        if partner != line.partner_at_time_of_submit:
            return HttpResponse(status=401)
        fulfilment_cart = cart
        if len(request.GET) != 0:
            fulfilment_cart_id = request.GET.get('cart', "")
            if fulfilment_cart_id:
                try:
                    fulfilment_cart = Cart.objects.get(id=fulfilment_cart_id)
                except Exception:
                    pass
        print(fulfilment_cart)
        line.fulfilled_in_cart = fulfilment_cart
        line.complete()
        line.save()
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Exception as e:
        print(e)
        return HttpResponse(status=400)


@login_required
def partner_order_status_update(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        partners, _ = past_cart.get_order_partners()
        if partner not in partners:
            return HttpResponse(status=403)
        past_cart.send_status_update()
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Cart.DoesNotExist:
        return HttpResponse(status=404)


def update_partner_comments(request, partner_slug, cart_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    try:
        past_cart = Cart.submitted.get(id=cart_id)
        partners, _ = past_cart.get_order_partners()
        if partner not in partners:
            return HttpResponse(status=403)
        if request.method == "POST":
            form = PartnerCommentsForm(request.POST, instance=past_cart)
            if form.is_valid():
                form.save()
                return HttpResponseRedirect(
                    reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
            else:
                return HttpResponse(status=400)
        return HttpResponse(status=400)

    except Cart.DoesNotExist:
        return HttpResponse(status=404)


def partner_split_line(request, cart_id, line_id, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    cart = Cart.objects.get(id=cart_id)
    try:
        line = cart.lines.get(id=line_id)
        if partner != line.partner_at_time_of_submit:
            return HttpResponse(status=401)
        split_num = 1
        if len(request.GET) != 0:
            split_num = request.GET.get('split_num', "1")
            if not split_num:
                split_num = 1
        split_num = int(split_num)
        line.split(split_num)
        return HttpResponseRedirect(
            reverse('partner_order_details', kwargs={'partner_slug': partner_slug, 'cart_id': cart_id}))
    except Exception as e:
        print(e)
        return HttpResponse(status=400)
