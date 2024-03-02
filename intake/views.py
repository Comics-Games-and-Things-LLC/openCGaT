import datetime

import barcode
from PIL import Image, ImageDraw, ImageFont
from barcode import Code128
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse

from partner.models import Partner, get_partner_or_401
from shop.forms import AddInventoryItemForm
from shop.models import Product, InventoryItem
from .forms import RefreshForm, AddForm, UploadInventoryForm, POForm, POLineForm, PricingRuleForm, PrintForm
from .models import Distributor, DistItem, PurchaseOrder, POLine, DistributorWarehouse, DistributorInventoryFile, \
    PricingRule


def index(request, partner_slug):
    return intake_item_view(request, None, partner_slug)


@login_required
def intake_item_view(request, barcode, partner_slug):
    partner = get_object_or_404(Partner, slug=partner_slug)
    if request.user not in partner.administrators.all():
        raise PermissionDenied
    print(request.method)
    add_mode = False
    auto_print = False
    quantity = None
    auto_load = None
    dist_list = Distributor.objects.all()
    distributor = dist_list.first()

    po_id = None
    po = None

    if request.method == 'POST':
        print(request.POST)
        form = RefreshForm(request.POST, partner=partner)
        if form.is_valid():
            barcode = form.cleaned_data.get('barcode')
            add_mode = form.cleaned_data.get('add_mode')
            auto_print = form.cleaned_data.get('auto_print_mode')
            auto_load = form.cleaned_data.get('auto_load')
            quantity = form.cleaned_data.get('quantity')
            distributor = form.cleaned_data.get('distributor')
            po_id = form.cleaned_data.get('purchase_order')
            print(form.cleaned_data)
        else:
            print("FORM INVALID")
            print(form.errors)

    print(barcode, quantity)
    try:
        distributor = dist_list.get(dist_name=distributor)
    except Exception as e:
        print(e)
    # print(add_mode)
    # print(auto_print)
    print(distributor)
    dist_items = None
    item = None
    local_product = None
    local_item = None
    count = None
    mfc_guess = None
    cat_guess = None
    print_x_on_load = 0
    if barcode:
        count = 0

        dist_items = DistItem.objects.filter(dist_barcode=barcode)
        try:
            local_product = Product.objects.get(barcode=barcode)
            local_item = InventoryItem.objects.filter(partner=partner, product=local_product).first()
        except Product.DoesNotExist:
            pass
        except InventoryItem.DoesNotExist:
            pass

        if local_item:
            reason = "Intake (no purchase order)"
            if add_mode:
                po = None
                if po_id and po_id != 'None':
                    po, created = PurchaseOrder.objects.get_or_create(partner=partner, po_number=po_id,
                                                                      distributor=distributor)
                    try:
                        po_item, po_item_created = POLine.objects.get_or_create(po=po, barcode=barcode)
                        po_item.received_quantity += quantity
                        po_item.save()
                        reason = "Intake: {}".format(po)
                    except Exception as e:
                        print(e)
                # adjust inventory
                local_item.adjust_inventory(quantity, reason=reason, purchase_order=po)
                count = local_item.get_inventory()
            else:
                count = local_item.get_inventory()
            if auto_print:
                print_x_on_load = quantity
        else:
            if add_mode:
                add_mode = 3
    context = {
        'refresh_form': RefreshForm(partner=partner),
        'add_form': AddForm(instance=local_product, partner=partner),
        'add_item_form': AddInventoryItemForm(instance=local_item, partner=partner, product=local_product),
        'dist_items': dist_items,
        'local_product': local_product,
        'local_item': local_item,
        'count': count,
        'add_mode': add_mode,
        'mfc_guess': mfc_guess,
        'cat_guess': cat_guess,
        'distributor': distributor,
        'dist_list': dist_list,
        'purchase_order': po_id,
        'po': po,
        'barcode': barcode,
        'auto_load': auto_load,
        'auto_print_enabled': auto_print,
        'partner': partner,
        'print_form': PrintForm(),
        'print_x_on_load': print_x_on_load,
    }
    if local_product:
        context.update(local_product.get_sold_info(partner=partner))

    return render(request, "intake/intake.html", context)


@login_required
def create_endpoint(request, partner_slug, barcode):
    partner = get_object_or_404(Partner, slug=partner_slug)
    if request.user not in partner.administrators.all():
        raise PermissionDenied
    if request.method == 'POST':
        print(request.POST)
        try:
            product = Product.objects.get(barcode=barcode)
        except Product.DoesNotExist:
            product = None
        form = AddForm(request.POST, instance=product, partner=partner)
        if form.is_valid():
            print("Form Valid")
            our_price = form.cleaned_data['our_price']
            try:
                new_product = form.save(commit=False)
                new_product.all_retail = True
                new_product.save()
                item = InventoryItem.objects.create(product=new_product, partner=partner, price=our_price,
                                                    default_price=our_price)
                item.save()
            except Product.DoesNotExist:
                return HttpResponse(status=201)
        else:
            print("FORM INVALID")
            print(form.errors)
            return HttpResponseBadRequest()


@login_required
def distributors(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    form = UploadInventoryForm()
    if request.POST:
        form = UploadInventoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('distributors', args={partner.slug}))
        else:
            print(form.errors)
    dist_data = {}

    for distributor in Distributor.objects.all():
        dist_data[distributor.dist_name] = {}
        try:
            for warehouse in DistributorWarehouse.objects.filter(distributor=distributor):
                try:
                    # See if distributor has warehouses
                    inventory = DistributorInventoryFile.objects.filter(warehouse=warehouse,
                                                                        distributor=distributor).latest('update_date')
                    dist_data[distributor.dist_name][warehouse.warehouse_name] = inventory
                except DistributorInventoryFile.DoesNotExist:
                    dist_data[distributor.dist_name][warehouse.warehouse_name] = "No warehouse inventory uploaded"
        except DistributorWarehouse.DoesNotExist:
            try:
                inventory = DistributorInventoryFile.objects.filter(distributor=distributor).latest('update_date')
                dist_data[distributor.dist_name]['inventory'] = inventory

            except DistributorInventoryFile.DoesNotExist:
                dist_data[distributor.dist_name][''] = None

    context = {
        'form': form,
        'distributors': dist_data,
        'partner': partner.slug,

    }
    return render(request, "intake/distributors.html", context)


FNTPATH = "intake/static/DroidSans.ttf"
fnt = ImageFont.truetype(FNTPATH, 100)
fnt_med = ImageFont.truetype(FNTPATH, 75)
fnt_small = ImageFont.truetype(FNTPATH, 50)


def generate_image(item):
    to_print = Image.new('L', (1000, 450), 'white')
    draw = ImageDraw.Draw(to_print)
    draw.text((0, 100), "Our Price:", font=fnt_med)  # currency field
    draw.text((500, 100), str("$" + str(item.default_price.amount)), font=fnt)  # currency field

    if item.product.name:

        draw.text((0, 225), item.product.name[:40], font=fnt_small)
        if len(item.product.name) > 40:
            draw.text((0, 275), item.product.name[40:], font=fnt_small)

    if item.product.msrp and item.product.msrp.amount != item.default_price.amount:
        draw.text((0, 0), "MSRP: $" + str(item.product.msrp.amount), font=fnt_med)
        price_start = draw.textlength("MSRP: $", font=fnt_med)

        l, t, r, b = draw.textbbox((price_start, 0), text=str(item.product.msrp.amount), font=fnt_med)
        # PIL 10.0.1 updated and replaced textsize with textbox, so we have to manually calculate the size
        draw.line(((l, b / 2 + 20), (r, t + 20)), width=5)

    if item.product.needs_barcode_printed:
        barcode_options = {'module_width': .4, 'module_height': 5}
        barcode_prerender = Code128(item.product.barcode, writer=barcode.writer.ImageWriter())
        barcode_image = barcode_prerender.render(writer_options=barcode_options)
        print(barcode_image.width, barcode_image.height)
        our_label = to_print
        to_print = Image.new('L', (1000, 450), 'white')
        to_print.paste(our_label)
        to_print.paste(barcode_image, (500 - round(barcode_image.width / 2), 325))
    else:
        draw.text((0, 350), item.partner.name, font=fnt_small)
    return to_print


@login_required
def get_image(request, partner_slug, item_id):
    item = get_object_or_404(InventoryItem, id=item_id)
    image = generate_image(item)
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG")
    return response


def pricing_rules_list(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    pricing_rules = PricingRule.objects.filter(partner=partner).order_by('priority')
    context = {
        'partner': partner,
        'rules': pricing_rules,
    }
    return TemplateResponse(request, "partner/pricing_rules.html", context)


def edit_rule(request, partner_slug, rule_id=None):
    partner = get_partner_or_401(request, partner_slug)

    form = PricingRuleForm()
    rule = None
    if rule_id:
        rule = get_object_or_404(PricingRule, id=rule_id)
        form = PricingRuleForm(instance=rule)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = PricingRuleForm(request.POST, instance=rule)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            new_rule = form.save(commit=False)
            new_rule.partner = partner
            new_rule.save()
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("pricing_rules", kwargs={'partner_slug': partner.slug}))
    context = {
        'form': form,
        'partner': partner,

    }
    return TemplateResponse(request, "create_from_form.html", context)


def po_list(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    purchase_orders = PurchaseOrder.objects.filter(partner=partner).order_by('-date')
    if not start_date:
        start_date = datetime.date.today() - datetime.timedelta(days=90)
    else:
        start_date = datetime.date.fromisoformat(start_date)  # Convert to format for template
    purchase_orders = purchase_orders.filter(date__gte=start_date)
    if end_date:
        end_date = datetime.date.fromisoformat(end_date)  # Convert to format for template

        purchase_orders = purchase_orders.filter(date__lte=end_date)
    if start_date or end_date:
        purchase_orders = (PurchaseOrder.objects.filter(date__isnull=True) | purchase_orders).distinct()
    context = {
        'partner': partner,
        'po_list': purchase_orders,
        'filter_start': start_date,
        'filter_end': end_date,
    }
    return TemplateResponse(request, "purchase_order/po_list.html", context)


def edit_po(request, partner_slug, po_id=None):
    partner = get_partner_or_401(request, partner_slug)

    form = POForm()
    po = None
    if po_id:
        po = get_object_or_404(PurchaseOrder, po_number=po_id)
        form = POForm(instance=po)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = POForm(request.POST, instance=po)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            po = form.save(commit=False)
            po.partner = partner
            po.save()
            if po.po_number != po_id:
                # Move any lines to the new purchase order
                POLine.objects.filter(po__po_number=po_id).update(po=po)
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("purchase_orders", kwargs={'partner_slug': partner.slug}))
    context = {
        'form': form,
        'partner': partner,

    }
    return TemplateResponse(request, "create_from_form.html", context)


def po_details(request, partner_slug, po_id):
    partner = get_partner_or_401(request, partner_slug)
    po = get_object_or_404(PurchaseOrder, po_number=po_id, partner=partner)
    context = {
        'partner': partner,
        'po': po,
        'lines': po.lines.order_by('line_number').all()
    }
    return TemplateResponse(request, "purchase_order/po_details.html", context)


def edit_po_line(request, partner_slug, po_id, po_line_id=None):
    partner = get_partner_or_401(request, partner_slug)
    po = get_object_or_404(PurchaseOrder, partner=partner, po_number=po_id)
    form = POLineForm(po=po)
    line = None
    if po_line_id:
        line = get_object_or_404(POLine, id=po_line_id)
        form = POLineForm(instance=line)

    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = POLineForm(request.POST, instance=line)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            line = form.save(commit=False)
            line.po = po
            line.save()
            # redirect to a new URL:
            return HttpResponseRedirect(reverse("po_details", kwargs={'partner_slug': partner.slug,
                                                                      'po_id': po.po_number}))
    context = {
        'form': form,
        'partner': partner,
        'line': line,
    }

    # I could consider moving this to the form, but then I wouldn't be able to add this to context.

    return TemplateResponse(request, "purchase_order/edit_po_line.html", context)


def delete_po(request, partner_slug, po_id, confirm=None):
    partner = get_partner_or_401(request, partner_slug)
    po = get_object_or_404(PurchaseOrder, partner=partner, po_number=po_id)

    next_url = reverse("purchase_orders", kwargs={'partner_slug': partner.slug})
    if int(confirm) == 1:
        po.delete()
        print("Deleting and forwarding")
        print(next_url)
        return HttpResponseRedirect(next_url)

    else:
        context = {
            'item_name': "PO {} {} on {}".format(po.distributor, po.po_number, po.date),
            'confirm_url': reverse('delete_po', kwargs={
                'partner_slug': partner.slug,
                'po_id': po_id,
                'confirm': 1,
            }),
            'back_url': next_url,
        }
        return TemplateResponse(request, "confirm_delete.html", context=context)


def delete_po_line(request, partner_slug, po_id, po_line_id, confirm=None):
    partner = get_partner_or_401(request, partner_slug)
    po = get_object_or_404(PurchaseOrder, partner=partner, po_number=po_id)

    next_url = reverse("po_details", kwargs={'partner_slug': partner.slug,
                                             'po_id': po_id})
    line = get_object_or_404(POLine, id=po_line_id, po=po)

    if int(confirm) == 1:
        line.delete()
        return HttpResponseRedirect(next_url)
    else:

        context = {
            'item_name': "{} from {}".format(line.name, line.po),
            'confirm_url': reverse('delete_po_line', kwargs={
                'partner_slug': partner.slug,
                'po_id': po_id,
                'po_line_id': po_line_id,
                'confirm': 1,
            }),
            'back_url': next_url,
        }
        return TemplateResponse(request, "confirm_delete.html", context=context)


def scan_item_to_po(request, partner_slug, po_id, barcode):
    partner = get_partner_or_401(request, partner_slug)
    po = get_object_or_404(PurchaseOrder, partner=partner, po_number=po_id)
    try:
        po_item, po_item_created = POLine.objects.get_or_create(po=po, barcode=barcode)
        po_item.received_quantity += 1
        po_item.save()
    except Exception as e:
        print(e)
    return HttpResponse(status=200)
