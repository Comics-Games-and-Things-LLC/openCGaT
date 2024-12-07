from datetime import datetime
from decimal import Decimal

import pypdf_table_extraction
from moneyed import Money
from pypdf import PdfReader

from intake.models import PurchaseOrder, Distributor, POLine
from shop.models import Product


def get_dist_object():
    return Distributor.objects.get(dist_name="Kingsley")


def read_pdf_invoice(pdf_path):
    info = get_invoice_summary(pdf_path)
    # Not strictly necessary to use distributor here as po_number is our primary key, but we will likely want to change that in the future.
    print("Invoice number:", info.invoice_number)
    po = PurchaseOrder.objects.get(po_number=info.invoice_number, distributor=get_dist_object())
    if not po.date:
        po.date = info.date
    if not po.subtotal:
        po.subtotal = Money(info.subtotal, get_dist_object().currency)
    print(po.subtotal)
    po.save()
    get_invoice_lines(pdf_path, po)


def get_invoice_lines(pdf_path, po):
    tables = pypdf_table_extraction.read_pdf(pdf_path,
                                             flavor='stream',
                                             pages="1-end",
                                             row_tol=20,
                                             )
    line_index = 0
    columns = ['Item Name', 'SKU', 'HS\nCode', 'COO', 'Unit Price', 'Quantity', 'Total', 'Total Tax']
    found_start = False

    for table in tables:
        for line in table.df.to_numpy():
            line = line.tolist()  # Numpy array to list
            if not found_start:
                if columns == line:
                    found_start = True
                continue

            try:
                line = {columns[i]: line[i] for i in range(len(line))}
            except Exception:
                continue

            if not line["Quantity"]:
                continue  # Skip lines that aren't full there.

            line_index += 1
            # At this point we now have a valid line
            line_info = InvoiceLineInfo(line)
            line_info.line_number = line_index

            if line_info.processing_error:
                print(line)
                print('\t', line_info.processing_error)
                continue

            barcode = find_barcode_from_product(line_info.sku, line_info.abridged_name)
            if not barcode:
                print(line)
                print('\t', f"Could not find a specific product with sku {line_info.sku} for {line_info.abridged_name}")
                continue

            po_lines = POLine.objects.filter(po=po, barcode=barcode)
            if po_lines.count() != 1:
                print(line)
                print('\t', f"Could not find a specific PO line for barcode {barcode} for {line_info.abridged_name}")
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

            po_line.save()
    print(f"{line_index} lines processed")


def find_barcode_from_product(sku, name):
    products = Product.objects.filter(publisher_sku=sku)
    if products.count() == 1:
        product = products.first()
        return product.barcode
    if not name:
        return None
    products = Product.objects.filter(name__search=name)
    if products.count() == 1:
        product = products.first()
        print(f"Assuming that {name} is {product.name}")
        return product.barcode


class InvoiceLineInfo:
    line_number = None
    qty_unit = None
    sku = None
    final_cost = None  # This is the real cost after discount, and what we want to use
    processing_error = None

    def __init__(self, line):
        self.qty_unit = line["Quantity"]
        self.abridged_name = line["Item Name"].replace('\n', " ")
        if "*" in self.abridged_name:
            self.abridged_name = self.abridged_name.split("*")[0]
        self.sku = line["SKU"].replace("\n", "")
        self.final_cost = Decimal(line["Unit Price"])

    @property
    def dist_code(self):
        return f"{self.abridged_name} {self.sku}"


class InvoiceInfo:
    subtotal = None
    date = None
    invoice_number = None


def get_invoice_summary(pdf_path):
    reader = PdfReader(pdf_path)

    info = InvoiceInfo()

    first_page = reader.pages[0]
    text = first_page.extract_text()
    for line in text.splitlines():
        if "Order Number" in line:
            [order_number, date] = line.split("Order Number: #")[1].split("Issue Date: ")
            date = date.strip()
            try:
                info.date = datetime.strptime(date.strip(), "%B %d, %Y")
            except ValueError:
                date = date.replace("Sept", "Sep")
                info.date = datetime.strptime(date.replace('.', ''), "%b %d, %Y")
            info.invoice_number = order_number.strip()

    last_page = reader.pages[-1]
    text = last_page.extract_text()
    for line in text.splitlines():
        print(line)
        if "Subtotal" in line:
            info.subtotal = line.split("Subtotal £")[1].strip()
    return info
