import csv
from datetime import datetime, timedelta

from allauth.account.models import EmailAddress
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, F, DecimalField
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404

from checkout.models import Cart, CheckoutLine
from digitalitems.models import DigitalItem
from partner.forms import FiltersForm, DiscountForm, BanForm, StaffLogPaymentForm
from partner.models import Partner, get_partner_or_401, PartnerTransaction
from shop.models import Item


def partner_info(request, partner_slug):
    partner = get_object_or_404(Partner, slug=partner_slug)
    context = {
        'partner_info': partner,
    }
    return render(request, "partner/partner_info.html", context)


@login_required
def partner_homepage(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    context = {
        'partner': partner,
    }
    return render(request, "partner/partner_homepage.html", context)


def partner_list(request):
    partners = Partner.objects.filter(hide=False).order_by('name')
    context = {
        'digital_list': partners.filter(digital_partner=True).exclude(retail_partner=True),
        'retail_list': partners.filter(retail_partner=True),
    }
    return render(request, "partner/partner_list.html", context)


@login_required
def partner_select(request):
    partners = request.user.admin_of.all().order_by('name')
    print(partners)
    context = {
        'partner_list': partners,
    }
    return render(request, "partner/partner_select.html", context)


@staff_member_required
def admin_billing(request):
    partners = Partner.objects.all()
    total = 0
    for partner in partners:
        total += partner.acct_balance
    context = {
        'partners': Partner.objects.all(),
        'balance': total,
    }
    return render(request, "partner/admin_billing.html", context)


def partner_billing(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug=partner_slug)

    form = StaffLogPaymentForm(initial={'type': PartnerTransaction.PAYMENT})
    if request.method == "POST":
        form = StaffLogPaymentForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.partner = partner
            transaction.save()

    billing_history = partner.partnertransaction_set.filter(summarized_in=None).order_by('-timestamp')
    paginator = Paginator(billing_history, 10)  # Show 25 contacts per page.
    page_number = int(request.GET.get('page_number', 1))
    page = paginator.get_page(page_number)
    context = {
        'partner': partner,
        'balance': partner.acct_balance,
        'page': page,
        'page_number': page_number,
        'staff_payment_log_form': form
    }
    return render(request, "partner/partner_billing.html", context)


def summary_breakout(request, partner_slug, summary_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)

    billing_history = partner.partnertransaction_set.filter(summarized_in=summary_id).order_by('-timestamp')
    paginator = Paginator(billing_history, 10)  # Show 25 contacts per page.
    page_number = int(request.GET.get('page_number', 1))
    page = paginator.get_page(page_number)
    context = {
        'partner': partner,
        'balance': partner.acct_balance,
        'summary_breakout': get_object_or_404(PartnerTransaction, id=summary_id),
        'page': page,
        'page_number': page_number,

    }
    return render(request, "partner/partner_billing.html", context)


@staff_member_required
def admin_summary_breakout(request, summary_id):
    billing_history = PartnerTransaction.objects.filter(summarized_in=summary_id).order_by('-timestamp')
    paginator = Paginator(billing_history, 10)  # Show 25 contacts per page.
    page_number = int(request.GET.get('page_number', 1))
    page = paginator.get_page(page_number)
    context = {
        'page': page,
        'page_number': page_number,
        'summary_breakout': get_object_or_404(PartnerTransaction, id=summary_id)
    }
    return render(request, "partner/admin_billing.html", context)


def update_billing(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    lines = CheckoutLine.objects.filter(item__partner=partner)
    orders = Cart.submitted.filter(lines__in=lines) \
             | Cart.submitted.filter(payment_partner=partner) | Cart.submitted.filter(pickup_partner=partner)
    for cart in orders.distinct():
        cart.pay_partners()
    partner.update_balance()

    return JsonResponse({'balance': str(partner.acct_balance)})


@staff_member_required
def admin_update_billing(request):
    # TODO: Remove these functions
    for partner in Partner.objects.all():
        orders = Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED])
        for cart in orders.distinct():
            partners, count = cart.get_order_partners()
            cart.pay_partner(partner, count)
        partner.update_balance()
    return HttpResponse(status=200)


@staff_member_required
def admin_reset_billing(request):
    for partner in Partner.objects.all():
        orders = Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED])
        for cart in orders.distinct():
            cart.reset_partner_payment(partner)
        partner.reset_balance()
        partner.update_balance()

    return HttpResponse(status=200)


def reset_billing(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    lines = CheckoutLine.objects.filter(item__partner=partner)
    orders = Cart.submitted.filter(lines__in=lines) \
             | Cart.submitted.filter(payment_partner=partner) | Cart.submitted.filter(pickup_partner=partner)
    for cart in orders.distinct():
        cart.reset_partner_payment(partner)
    partner.reset_balance()
    partner.update_balance()

    return JsonResponse({'balance': str(partner.acct_balance)})


@staff_member_required
def admin_customer_list(request):
    return customer_list(request, admin=True)


def customer_list(request, partner_slug=None, admin=False):
    partner = None
    if not admin:
        partner = get_partner_or_401(request, partner_slug=partner_slug)

    customers = get_user_model().objects.all().order_by(F("last_login").desc(nulls_last=True))

    form = FiltersForm()
    if request.method == 'GET':
        form = FiltersForm(request.GET)
        if form.is_valid():
            search_string = form.cleaned_data.get("search")
            if search_string:
                username_customers = customers.filter(username__icontains=search_string)
                email_addresses = EmailAddress.objects.filter(email__icontains=search_string)
                customers = username_customers | customers.filter(id__in=email_addresses.values_list('user_id'))

    paginator = Paginator(customers, 10)  # Show 25 contacts per page.
    page_number = int(request.GET.get('page_number', 1))
    page = paginator.get_page(page_number)

    context = {
        'form': form,
        'partner': partner,
        'admin': admin,
        'page': page,
        'page_number': page_number,
    }
    return render(request, "partner/customer_list.html", context)


def customer_details(request, partner_slug, user_id):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    customer = get_object_or_404(get_user_model(), id=user_id)
    if request.method == "POST":
        form = BanForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
    lines = CheckoutLine.objects.filter(item__partner=partner)
    orders = Cart.submitted.filter(lines__in=lines) \
             | Cart.submitted.filter(payment_partner=partner) | Cart.submitted.filter(pickup_partner=partner)
    orders = orders.distinct().order_by('date_submitted')
    campaigns = {}
    context = {
        'partner': partner,
        'customer': customer,
        'orders': orders.filter(owner=customer),
        'items': DigitalItem.objects.filter(downloads__user=customer, partner__slug=partner_slug),
        'banform': BanForm(instance=customer),
        'campaigns': campaigns
    }
    return render(request, "partner/customer_details.html", context)


@staff_member_required()
def admin_customer_details(request, user_id):
    customer = get_object_or_404(get_user_model(), id=user_id)
    if request.method == "POST":
        form = BanForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
    orders = Cart.objects.filter(owner=customer).distinct().order_by('date_submitted')
    context = {
        'customer': customer,
        'orders': orders,
        'items': DigitalItem.objects.filter(downloads__user=customer),
        'banform': BanForm(instance=customer),
        'admin': True,
    }
    return render(request, "partner/customer_details.html", context)


def discount_all(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug=partner_slug)

    form = DiscountForm()
    if request.method == "POST":
        form = DiscountForm(request.POST)
        if form.is_valid():
            multiplier = form.cleaned_data['multiplier']
            items = Item.objects.filter(partner=partner)
            if form.cleaned_data['publisher']:
                print(form.cleaned_data['publisher'])
                items = Item.objects.filter(product__publisher=form.cleaned_data['publisher'])
            for item in items:
                if form.cleaned_data['base_on_msrp'] and item.product.msrp:
                    item.price = item.product.msrp * multiplier
                else:
                    item.price = item.default_price * multiplier
                item.save()

    context = {
        'partner': partner,
        'form': form,
    }
    return render(request, "partner/partner_discount_all.html", context)


def financial(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    lines = CheckoutLine.objects.filter(item__partner=partner, cart__status__in=[Cart.PAID, Cart.COMPLETED])

    context = {
        'partner': partner,
        'all_time': sum_lines(lines),
        'month_to_date': sum_lines(lines.filter(cart__date_paid__gte=datetime.today().replace(day=1))),
        'four_weeks': sum_lines(lines.filter(cart__date_paid__gte=datetime.today() - timedelta(days=28)))
    }
    return render(request, "partner/partner_financials.html", context)


def sum_lines(lines):
    return lines.aggregate(total=Sum(F('quantity') * F('price_per_unit_at_submit'), output_field=DecimalField()))[
        'total']


def export_pt_sales_csv(request, partner_slug):
    return export_pt_csv(request, partner_slug, sales_only=True)


def export_pt_csv(request, partner_slug, sales_only=False):
    partner = get_partner_or_401(request, partner_slug=partner_slug)
    output_name = "{} CG&T {}.csv".format(partner.name, datetime.today())
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="{}"'.format(output_name)},
    )

    create_csv(partner, response, sales_only)
    return response


def create_csv(partner, file, sales_only=False, print_count=False):
    fieldnames = ['Timestamp', 'Type', 'Cart Number', 'Contact Info', 'Cart Total (includes VAT)', 'Tax/VAT Collected',
                  'Partner Subtotal', 'Platform Fees', "Partner Net", "Balance After Applied",
                  'Address', 'Country', "State", "Post Code"]
    writer = csv.DictWriter(file, fieldnames=fieldnames)

    writer.writeheader()
    transactions = partner.partnertransaction_set.filter(is_summary=False).order_by('-timestamp')
    if sales_only:
        transactions = transactions.filter(type=PartnerTransaction.PURCHASE)
    if print_count:
        total_count = transactions.count()
        print("Printing {} transactions".format(transactions.count()))
        count = 1
    for transaction in transactions:
        if print_count:
            print("{}/{}".format(count, total_count))
            count += 1
        line_info = {"Timestamp": transaction.timestamp, "Type": transaction.type,
                     "Partner Subtotal": transaction.transaction_subtotal,
                     "Platform Fees": transaction.transaction_fees,
                     "Partner Net": transaction.partner_cut,
                     "Balance After Applied": transaction.balance_after_apply,
                     }

        carts = Cart.submitted.filter(partner_transactions=transaction.id)
        if carts.exists():
            cart = carts.first()
            line_info.update({'Cart Number': cart.id,
                              "Contact Info": cart.owner if cart.owner else cart.email,
                              "Tax/VAT Collected": cart.final_tax, "Cart Total (includes VAT)": cart.final_total,
                              })
            country, postcode, potential_address, state = get_address_or_old_address(cart)

            line_info["Address"] = str(potential_address)
            line_info["Country"] = country
            line_info["State"] = state
            line_info["Post Code"] = postcode

        writer.writerow(line_info)
    return file


def get_address_or_old_address(cart):
    potential_address = cart.get_tax_address()
    old_address = False
    country = None
    state = None
    postcode = None
    if potential_address is None:
        potential_address = cart.old_billing_address if cart.old_billing_address else cart.delivery_address
        if cart.payment_method == cart.PAY_IN_STORE:
            if cart.payment_partner is not None:
                potential_address = cart.payment_partner.address
        elif cart.is_shipping_required():
            if cart.delivery_method == cart.PICKUP_ALL:
                if cart.pickup_partner is not None:
                    potential_address = cart.pickup_partner.address
            elif cart.delivery_method == cart.SHIP_ALL:
                if cart.shipping_address is not None:
                    potential_address = cart.delivery_address
                    old_address = True
        if potential_address is None:
            potential_address = cart.old_billing_address
            old_address = True
    if old_address and potential_address:
        addr = potential_address.as_dict()
        try:
            country = addr["country_code"]
        except KeyError:
            pass
        try:

            state = addr["state_code"]
        except KeyError:
            pass
        try:
            postcode = addr['postal_code']
        except KeyError:
            pass

    else:
        try:
            country = potential_address.country.code
            state = potential_address.state
            postcode = potential_address.postcode
        except AttributeError:
            pass
    return country, postcode, potential_address, state
