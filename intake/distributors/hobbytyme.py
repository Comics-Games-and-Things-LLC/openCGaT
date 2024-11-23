from datetime import datetime

import camelot
from moneyed import Money
from pypdf import PdfReader

from intake.models import PurchaseOrder, Distributor, POLine
from shop.models import Product


def get_dist_object():
    return Distributor.objects.get(dist_name="Hobbytyme")


def read_pdf_invoice(pdf_path):
    info = get_invoice_summary(pdf_path)
    # Not strictly necessary to use distributor here as po_number is our primary key, but we will likely want to change that in the future.

    po = PurchaseOrder.objects.get(po_number=info.invoice_number, distributor=get_dist_object())
    if not po.amount_charged:
        po.amount_charged = Money(info.final_total, 'USD')
    if not po.date:
        po.date = datetime.strptime(info.date, '%m/%d/%y')
    if not po.subtotal:
        po.subtotal = Money(info.pre_additional_discount, "USD") - Money(info.shipping_and_handling, "USD") \
                      + Money(info.additional_discount,
                              'USD')  # Additional discount is negative, so adding it is subtracting it.
    print(po.subtotal)
    po.save()

    get_invoice_lines(pdf_path, po)


def get_invoice_lines(pdf_path, po):
    tables = camelot.read_pdf(pdf_path,
                              flavor='stream',
                              pages="1-end"
                              )
    line_index = 0
    for table in tables:
        found_start = False
        for line in table.df.to_numpy():
            line = line.tolist()  # Numpy array to list
            if not found_start:
                if "LINE|QTY / UM|" in "|".join(line):
                    found_start = True
                continue
            line_number = line[0]
            try:
                line_number = int(line_number)
            except ValueError:
                continue
            if line_number != line_index + 1:
                continue
            line_index += 1
            if "HTM/WEB" in line and "Thank You For The Order!!!" in line:
                continue  # This is a thank you line we can ignore.

            # At this point we now have a valid line
            line_info = InvoiceLineInfo(line)
            if line_info.qty_type == "BX":
                print("Not sure how to handle boxes, skipping line:")
                print('\t', line)
                continue
            barcode = find_barcode_from_sku(line_info.sku)
            if not barcode:
                print(f"Could not find a specific product with sku {line_info.sku} for line:")
                print('\t', line)
                continue
            po_lines = POLine.objects.filter(po=po, barcode=barcode)
            if po_lines.count() != 1:
                print(f"Could not find a specific PO line for barcode {barcode} on line:")
                print('\t', line)
                continue
            po_line = po_lines.first()
            po_line.distributor_code = line_info.dist_code
            if not po_line.line_number:
                po_line.line_number = line_info.line_number
            if not po_line.expected_quantity:
                po_line.expected_quantity = int(line_info.qty_of_type)
            if not po_line.cost_per_item:
                po_line.cost_per_item = Money(line_info.final_cost, "USD")
            po_line.save()


def find_barcode_from_sku(sku):
    products = Product.objects.filter(publisher_sku=sku)
    if products.count() == 1:
        return products.order_by("-release_date").first().barcode


class InvoiceLineInfo:
    line_number = None
    qty_of_type = None
    qty_type = None
    dist_code = None
    mfc_code = None
    sku = None
    retail_price = None
    first_cost = None
    final_cost = None
    ext_before_discount = None
    other_discount = False

    def __init__(self, line):
        self.line_number = int(line[0])
        qty_and_qty_type = line[1]
        self.qty_of_type = qty_and_qty_type.split(" ")[0]
        self.qty_type = qty_and_qty_type.split(" ")[-1]  # Using last because there can be multiple spaces
        mfc_and_sku_and_abridged_name = line[2]

        self.mfc_code = mfc_and_sku_and_abridged_name.split("/")[0]
        self.sku = mfc_and_sku_and_abridged_name.split("/")[1].split(" ")[0]

        abridged_name = mfc_and_sku_and_abridged_name.split(self.dist_code)[1].strip()
        self.retail_price = line[3]
        self.first_cost = line[4]
        self.final_cost = line[5]
        self.ext_before_discount = line[6]
        if len(line) > 7:
            self.other_discount = line[7] == "*"

    @property
    def dist_code(self):
        return f"{self.mfc_code}/{self.sku}"


class InvoiceInfo:
    final_total_with_commas = None
    total_cost_of_merchandise = None
    shipping_and_handling = None
    pre_additional_discount = None
    additional_discount = None
    final_total = None
    date = None
    invoice_number = None


def get_invoice_summary(pdf_path):
    customer_number = "039015"
    reader = PdfReader(pdf_path)
    page = reader.pages[-1]
    text = page.extract_text()
    charge_information_index = 0
    info = InvoiceInfo()
    for line in text.splitlines():
        if customer_number in line:
            if not (customer_number == line.strip().split(' ')[0]):
                raise Exception("Customer number not where we expected")
            info.date = line.strip().split(' ')[1]
            info.invoice_number = line.strip().split(' ')[2]

        if "CREDIT CARD AMOUNT:" in line:
            charge_information_index = 1
            # The line looks like:
            # *** PAID BY CREDIT CARD #: xxxx-xxxx-xxxx-xxxx  CREDIT CARD AMOUNT:   1,107.11 ***
            info.final_total_with_commas = line.split("CREDIT CARD AMOUNT:")[1].strip()[:-3].strip()
        if charge_information_index == 2:
            info.total_cost_of_merchandise = line.strip().split(' ')[-1]
        if charge_information_index == 3:
            info.shipping_and_handling = line.strip().split(' ')[-1]
        if charge_information_index == 4:
            info.pre_additional_discount = line.strip().split(' ')[-1]
        if charge_information_index == 5:
            info.additional_discount = line.strip().split(' ')[-1]
        if charge_information_index == 6:
            info.final_total = line.strip().split(' ')[-1]
        if charge_information_index:
            charge_information_index += 1
    return info
