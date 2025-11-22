from datetime import datetime
from decimal import Decimal

import pypdf_table_extraction
from moneyed import Money
from pypdf import PdfReader

from intake.distributors import vallejo
from intake.models import PurchaseOrder, Distributor, POLine
from shop.models import Product


def get_dist_object():
    return Distributor.objects.get(dist_name="Hobbytyme")


def read_pdf_invoice(pdf_path):
    info = get_invoice_summary(pdf_path)
    # Not strictly necessary to use distributor here as po_number is our primary key, but we will likely want to change that in the future.
    print("Invoice number:", info.invoice_number)
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

    return po, get_invoice_lines(pdf_path, po)


def get_invoice_lines(pdf_path, po):
    tables = pypdf_table_extraction.read_pdf(pdf_path,
                                             flavor='stream',
                                             pages="1-end"
                                             )
    could_not_process_lines = []

    columns = ["Line", "QTY/UM", "MFG / ITEM NO. and DESCRIPTION", "RETAIL PRICE", "FIRST COST", "FINAL COST",
               "EXT BEFORE DISCOUNT", ""]  # Sometimes there's an extra blank column

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
            if "HTM/WEB" in line[2] and "Thank You For The Order!!!" in line[2]:
                continue  # This is a 'thank you' line we can ignore.

            # At this point we now have a valid line
            line_info = InvoiceLineInfo(line)
            try:  # Turn line into a dictionary for nice output
                line = {columns[i]: line[i] for i in range(len(line))}
            except Exception as e:
                print(f"Could not parse line {line_number}: {line}: error: {e}")
                continue

            if line_info.qty_of_type == "0":
                continue  # Skip lines of quantity 0 (backorders).

            if line_info.processing_error:
                print(line)
                print('\t', line_info.processing_error)
                could_not_process_lines.append(line)
                continue

            if (line_info.qty_type == "BX" and
                    not (line_info.mfc_code in ["VAL", "TAM", "GNZ"])):
                print(line)
                print('\t', "Not sure how to handle boxes not of Vallejo, Tamiya, or Mr Hobby, skipping line")
                could_not_process_lines.append(line)
                continue

            barcode = find_barcode_from_sku(line_info.mfc_code, line_info.sku)
            if not barcode:
                print(line)
                print('\t', f"Could not find a specific product with sku {line_info.sku} for {line_info.abridged_name}")
                could_not_process_lines.append(line)
                continue

            po_lines = POLine.objects.filter(po=po, barcode=barcode)
            if po_lines.count() != 1:
                print(line)
                print('\t', f"Could not find a specific PO line for barcode {barcode} for {line_info.abridged_name}")
                could_not_process_lines.append(line)
                continue

            po_line = po_lines.first()
            po_line.distributor_code = line_info.dist_code
            if not po_line.line_number:
                po_line.line_number = line_info.line_number
            elif po_line.line_number != line_info.line_number:
                print(f"{line}\n\tLine number differs!")
            if not po_line.expected_quantity:
                po_line.expected_quantity = int(line_info.qty_unit)
            elif po_line.expected_quantity != int(line_info.qty_unit):
                print(f"{line}\n\tExpected Quantity differs!")
            if not po_line.cost_per_item:
                po_line.cost_per_item = Money(line_info.final_cost, "USD")
            elif po_line.cost_per_item != Money(line_info.final_cost, "USD"):
                print(f"{line}\n\tCost differs! Calculated to be {line_info.final_cost}")
            if not po_line.msrp_on_line:
                po_line.msrp_on_line = Money(line_info.retail_price, "USD")
            elif po_line.msrp_on_line != Money(line_info.retail_price, "USD"):
                print(f"{line}\n\tMSRP differs! Calculated to be {line_info.retail_price}")

            po_line.save()
    return could_not_process_lines


def find_barcode_from_sku(mfc_code, sku):
    if mfc_code == "VAL" and "EX" not in sku:  # Ignore racks, etc
        return vallejo.get_barcode_from_sku(sku)
    else:
        products = Product.objects.filter(publisher_sku=sku)

    if products.count() == 1:
        return products.order_by("-release_date").first().barcode


class InvoiceLineInfo:
    line_number = None
    qty_of_type = None
    qty_type = None
    qty_unit = None
    mfc_code = None
    sku = None
    abridged_name = None
    retail_price = None
    first_cost = None
    final_cost = None  # This is the real cost after discount, and what we want to use
    ext_before_discount = None
    other_discount = False
    processing_error = None

    def __init__(self, line):
        self.line_number = int(line[0])
        qty_and_qty_type = line[1]
        self.qty_of_type = qty_and_qty_type.split(" ")[0]
        self.qty_type = qty_and_qty_type.split(" ")[-1]  # Using last because there can be multiple spaces
        mfc_and_sku_and_abridged_name = line[2]
        self.mfc_code = mfc_and_sku_and_abridged_name.split("/")[0]
        self.sku = mfc_and_sku_and_abridged_name.split("/")[1].split(" ")[0]

        self.abridged_name = mfc_and_sku_and_abridged_name.split(self.dist_code)[1].strip()
        qty_per_type = 1
        if self.qty_type == "BX":
            qty_text = self.abridged_name.split(" ")[-1]  # Last word is ideally a quantity marker
            if qty_text.endswith("p"):
                qty_per_type = int(qty_text[:-1])  # 6p
            elif qty_text.endswith("pk"):
                qty_per_type = int(qty_text[:-2])  # 6pk
            elif "@" in qty_text[-1]:
                qty_per_type = int(qty_text.split("@")[0])  # 6@$7.50
            elif self.dist_code in ["GNZ/MC129", "TAM/87038", "TAM/87182"]:  # revert to hardcoded check
                qty_per_type = 6
            else:
                self.processing_error = f"Unable to determine quantity for line {self.line_number}"
                return
        if qty_per_type > 1:
            print(f"We determined {self.abridged_name} has a quantity of {qty_per_type}")
        self.qty_unit = int(self.qty_of_type) * qty_per_type

        self.ext_before_discount = Decimal(line[6]) / qty_per_type

        if self.ext_before_discount > 0:  # These could be empty, so check the subtotal first.
            self.retail_price = Decimal(line[3]) / qty_per_type
            self.first_cost = Decimal(line[4]) / qty_per_type
            self.final_cost = Decimal(line[5]) / qty_per_type

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
            line_past_customer_number = line.strip().split(customer_number)[1].strip()
            info.date = line_past_customer_number.split(' ')[0]
            info.invoice_number = line_past_customer_number.split(' ')[1]

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
