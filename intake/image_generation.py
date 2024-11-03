import datetime

import barcode
from PIL import Image, ImageDraw, ImageFont
from barcode import Code128

from checkout.models import CheckoutLine

image_width = 1000
image_height = int(image_width * 450 / 1000)


def pct_w(percent):
    return int(image_width * percent / 100)


def pct_h(percent):
    return int(image_height * percent / 100)


FNTPATH = "intake/static/DroidSans.ttf"
fnt = ImageFont.truetype(FNTPATH, pct_h(22))
fnt_xl = ImageFont.truetype(FNTPATH, pct_h(50))
fnt_med = ImageFont.truetype(FNTPATH, pct_h(15))
fnt_small = ImageFont.truetype(FNTPATH, pct_h(11))


def draw_multiline_text(draw, name, pct_h_start):
    draw.text((0, pct_h(pct_h_start)), name[:39], font=fnt_small)
    if len(name) > 39:
        draw.text((0, pct_h(pct_h_start + 11)), name[39:].strip(), font=fnt_small)


def generate_product_sticker(item):
    to_print = Image.new('L', (image_width, image_height), 'white')
    draw = ImageDraw.Draw(to_print)

    if item.product.msrp and item.product.msrp.amount != item.default_price.amount:
        draw.text((0, 0), "MSRP: $" + str(item.product.msrp.amount), font=fnt_med)
        price_start = draw.textlength("MSRP: $", font=fnt_med)

        l, t, r, b = draw.textbbox((price_start, 0), text=str(item.product.msrp.amount), font=fnt_med)
        # PIL 10.0.1 updated and replaced textsize with textbox, so we have to manually calculate the size
        draw.line(((l, b / 2 + 20), (r, t + 20)), width=5)

    draw.text((0, 100), "Our Price:", font=fnt_med)  # currency field
    draw.text((pct_w(50), 100), str("$" + str(item.default_price.amount)), font=fnt)  # currency field

    draw_multiline_text(draw, item.product.name, 50)

    if item.product.needs_barcode_printed:
        barcode_options = {'module_width': .4, 'module_height': 5}
        barcode_prerender = Code128(item.product.barcode, writer=barcode.writer.ImageWriter())
        barcode_image = barcode_prerender.render(writer_options=barcode_options)
        print(barcode_image.width, barcode_image.height)
        our_label = to_print
        to_print = Image.new('L', (image_width, image_height), 'white')
        to_print.paste(our_label)
        to_print.paste(barcode_image, (500 - round(barcode_image.width / 2), 325))
    else:
        draw.text((0, 350), item.partner.name, font=fnt_small)
    return to_print


def generate_image_for_order(line: CheckoutLine):
    item = line.item

    to_print = Image.new('L', (image_width, image_height), 'white')

    draw = ImageDraw.Draw(to_print)
    if line.cart.is_paid:
        draw.text((0, 0), "PAID", font=fnt_xl)

    draw.text((pct_w(50), 0), str(line.cart.id), font=fnt_med)

    other_addendum = ""
    other_items = line.cart.get_other_items_for_customer(paid_only=True)
    if other_items is not None:
        count = other_items.filter(ready=True).count()
        if count > 0:
            other_addendum = f"+ {count}"

    if line.cart.num_items > 1 or other_addendum:
        draw.text((pct_w(50), pct_h(20)),
                  f"{line.cart.num_ready_items} / {line.cart.num_active_items} {other_addendum}",
                  font=fnt_med)

    draw.text((pct_w(50), pct_h(40)), str(line.cart.delivery_method), font=fnt_med)

    if line.cart.owner:
        draw_multiline_text(draw, str(line.cart.owner), 50)
    draw_multiline_text(draw, str(line.cart.get_order_email()), 61)

    draw_multiline_text(draw, item.product.name, 75)
    if item.product.release_date > datetime.date.today():
        draw.text((pct_w(75), pct_h(0)), item.product.release_date.strftime("%d/%m/%y"), font=fnt_small)

    return to_print
