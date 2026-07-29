import re
from datetime import datetime
from decimal import Decimal

import pypdf_table_extraction
import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from moneyed import Money
from pypdf import PdfReader

from intake.models import PurchaseOrder, Distributor, POLine

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/150.0.0.0 Safari/537.36',
}


def get_dist_object():
    return Distributor.objects.get(dist_name="Hobbytyme")


def read_pdf_invoice(invoice_source):
    from intake.models import PoInvoiceFile
    if isinstance(invoice_source, PoInvoiceFile):
        pdf_file = invoice_source.file
    else:
        pdf_file = invoice_source
    info = get_invoice_summary(pdf_file)
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

    return po, get_invoice_lines(pdf_file, po)


def record_issue(line, message, lines_with_issues):
    print(line)
    print('\t', message)
    if line.get("Processing Note"):
        line["Processing Note"] = f"{line['Processing Note']}; {message}"
    else:
        line["Processing Note"] = message
    if line not in lines_with_issues:
        lines_with_issues.append(line)


def get_invoice_lines(pdf_file, po):
    tables = pypdf_table_extraction.read_pdf(pdf_file,
                                             flavor='stream',
                                             pages="1-end"
                                             )
    lines_with_issues = []

    columns = ["Line", "QTY/UM", "MFG / ITEM NO. and DESCRIPTION", "RETAIL PRICE", "FIRST COST", "FINAL COST",
               "EXT BEFORE DISCOUNT",
               "Other Discount",
               "Processing Note"]  # Sometimes there's an extra blank column with a * indicating discount

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
                if "Other Discount" not in line.keys():
                    line["Other Discount"] = ""  # Populate this value by default if needed
            except Exception as e:
                message = f"Could not parse line {line_number}: {line}: error: {e}"
                record_issue(line, message, lines_with_issues)
                continue

            if line_info.qty_of_type == "0":
                continue  # Skip lines of quantity 0 (backorders).

            if line_info.qty_per_type > 1:
                message = f"We determined {line_info.abridged_name} has a quantity of {line_info.qty_per_type}"
                record_issue(line, message, lines_with_issues)

            if line_info.processing_error:
                record_issue(line, line_info.processing_error, lines_with_issues)
                continue

            if (line_info.qty_type == "BX" and
                    not (line_info.mfc_code in ["VAL", "TAM", "GNZ"])):
                message = "Not sure how to handle boxes not of Vallejo, Tamiya, or Mr Hobby, skipping line"
                record_issue(line, message, lines_with_issues)
                continue

            barcode = find_barcode_from_sku(line_info.mfc_code, line_info.sku)
            if not barcode:
                message = f"Could not find a specific product with sku {line_info.sku} for {line_info.abridged_name}"
                record_issue(line, message, lines_with_issues)
                continue

            po_lines = POLine.objects.filter(po=po, barcode=barcode)
            if po_lines.count() != 1:
                message = f"Could not find a specific PO line for barcode {barcode} for {line_info.abridged_name}"
                record_issue(line, message, lines_with_issues)
                continue

            po_line = po_lines.first()
            po_line.distributor_code = line_info.dist_code
            if not po_line.line_number:
                po_line.line_number = line_info.line_number
            elif po_line.line_number != line_info.line_number:
                record_issue(line, "Line number differs!", lines_with_issues)
            if not po_line.expected_quantity:
                po_line.expected_quantity = int(line_info.qty_unit)
            elif po_line.expected_quantity != int(line_info.qty_unit):
                record_issue(line, "Expected Quantity differs!", lines_with_issues)
            if not po_line.cost_per_item:
                po_line.cost_per_item = Money(line_info.final_cost, "USD")
            elif po_line.cost_per_item != Money(line_info.final_cost, "USD"):
                record_issue(line, f"Cost differs! Calculated to be {line_info.final_cost}", lines_with_issues)
            if not po_line.msrp_on_line:
                po_line.msrp_on_line = Money(line_info.retail_price, "USD")
            elif po_line.msrp_on_line != Money(line_info.retail_price, "USD"):
                record_issue(line, f"MSRP differs! Calculated to be {line_info.retail_price}", lines_with_issues)

            po_line.save()
    return lines_with_issues


def find_barcode_from_sku(mfc_code, sku):
    from intake.models import DistItem
    dist_item, _ = DistItem.objects.get_or_create(distributor=get_dist_object(), dist_number=f"{mfc_code}/{sku}")
    dist_item.set_product_from_sku()
    if dist_item.product:
        return dist_item.product.barcode


class InvoiceLineInfo:
    line_number = None
    qty_of_type = None
    qty_type = None
    qty_unit = None
    qty_per_type = 1
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
        self.qty_per_type = 1
        if self.qty_type == "BX":
            qty_text = self.abridged_name.split(" ")[-1]  # Last word is ideally a quantity marker
            if qty_text.endswith("p"):
                self.qty_per_type = int(qty_text[:-1])  # 6p
            elif qty_text.endswith("pk"):
                self.qty_per_type = int(qty_text[:-2])  # 6pk
            elif "@" in qty_text[-1]:
                self.qty_per_type = int(qty_text.split("@")[0])  # 6@$7.50
            elif self.dist_code in ["GNZ/MC129", "TAM/87038", "TAM/87182"]:  # revert to hardcoded check
                self.qty_per_type = 6
            else:
                self.processing_error = f"Unable to determine quantity for line {self.line_number}"
                return
        if self.qty_per_type > 1:
            # This is an informational note, not necessarily an issue, but let's keep it as print for now.
            # However, the user said "All the warnings that don't currently add to lines_with_issues should go into lines_with_issues as well."
            # This is arguably a note about how we processed it.
            # But line dict is not available here.
            print(f"We determined {self.abridged_name} has a quantity of {self.qty_per_type}")
        self.qty_unit = int(self.qty_of_type) * self.qty_per_type

        self.ext_before_discount = Decimal(line[6]) / self.qty_per_type

        if self.ext_before_discount > 0:  # These could be empty, so check the subtotal first.
            self.retail_price = Decimal(line[3]) / self.qty_per_type
            self.first_cost = Decimal(line[4]) / self.qty_per_type
            self.final_cost = Decimal(line[5]) / self.qty_per_type

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


def get_invoice_summary(pdf_file):
    customer_number = "039015"
    reader = PdfReader(pdf_file)
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


def get_hobbytyme_session(auth):
    username = auth.username
    password = auth.password
    session = requests.Session()
    # The base URL that redirects to login and provides the refresh key
    base_url = "https://hobbytyme.com/dealers/index.cfm"

    # Headers from HAR to be more realistic
    headers = DEFAULT_HEADERS.copy()

    try:
        # Step 1: GET the base page to establish session cookies and get refresh key via redirect
        response = session.get(base_url, headers=headers)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        return_path_input = soup.find('input', {'name': 'returnPath'})
        refresh = None
        if return_path_input:
            value = return_path_input.get('value', '')
            refresh_match = re.search(r'refresh=(\d+)', value)
            if refresh_match:
                refresh = refresh_match.group(1)

        if not refresh:
            # Fallback to regex on whole page
            refresh_match = re.search(r'refresh=(\d+)', response.text)
            if refresh_match:
                refresh = refresh_match.group(1)

        if not refresh:
            return None

        # Update headers with Referer for POST
        headers['Referer'] = response.url

        # Prepare credentials
        post_data = {
            'action': 'welcome',
            'returnPath': f'/dealers/index.cfm?refresh={refresh}&',
            'loginUsername': username,
            'loginPassword': password,
            'submit_btn': '.'
        }

        # Step 2: POST credentials to authenticate
        session.post(base_url, data=post_data, headers=headers)

        # Check if we are authenticated
        backorders_url = "https://hobbytyme.com/dealers/index.cfm?action=myAccount.backorders"
        response = session.get(backorders_url, headers=headers)
        if response.status_code == 200 and "loginPassword" not in response.text:
            return session
    except Exception:
        pass
    return None


def fetch_hobbytyme_pages(session, url, headers, post_data=None):
    current_url = url
    while current_url:
        if post_data:
            print(f"POSTing to {current_url}")
            response = session.post(current_url, data=post_data, headers=headers)
            post_data = None  # Only POST for the first page
        else:
            print(f"Fetching {current_url}")
            response = session.get(current_url, headers=headers)

        if response.status_code != 200:
            print(f"Failed to fetch {current_url}")
            break
        soup = BeautifulSoup(response.text, 'html.parser')
        yield soup, response.url

        # Look for next page
        # Hobbytyme often uses "Next" text or a button with an arrow
        next_link = soup.find('a', string="»")

        if next_link and next_link.get('href'):
            next_url = next_link.get('href')
            if not next_url.startswith('http'):
                from urllib.parse import urljoin
                next_url = urljoin(current_url, next_url)

            if next_url == current_url:  # Avoid infinite loops
                break
            current_url = next_url
        else:
            current_url = None


def scrape_hobbytyme_tables(soup):
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        if not rows:
            continue

        # Find the header row
        header = None
        header_row_idx = -1
        for i, row in enumerate(rows):
            potential_header = [ele.text.strip().lower() for ele in row.find_all(['th', 'td'])]
            if any(h in potential_header for h in ["item #", "part number", "item no", "part #"]):
                header = potential_header
                header_row_idx = i
                break

        if header is None:
            continue

        def get_idx(names):
            for name in names:
                name_lower = name.lower()
                # Try exact match first
                if name_lower in header:
                    return header.index(name_lower)
                # Try partial match
                for i, h in enumerate(header):
                    if name_lower in h:
                        return i
            return None

        idx_mfc = get_idx(["manufacturer", "mfg"])
        idx_item = get_idx(["item #", "part number", "item no", "part #"])
        idx_desc = get_idx(["product", "description", "item description", "name"])
        idx_msrp = get_idx(["list price", "price"])
        idx_price = get_idx(["net price"])
        idx_qty = get_idx(["qty", "quantity"])
        idx_avail = get_idx(["avail", "avail."])
        idx_orders_due = get_idx(["date guaranteed", "orders due", "date ordered"])
        idx_announced = get_idx(["date announced", "announced"])
        idx_expected = get_idx(["date expected", "expected"])

        if idx_item is None:
            continue

        for row in rows[header_row_idx + 1:]:
            cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
            if len(cols) <= idx_item:
                continue

            data = {
                'manufacturer': cols[idx_mfc] if idx_mfc is not None else None,
                'item_number': cols[idx_item] if idx_item is not None else None,
                'description': cols[idx_desc] if idx_desc is not None else None,
                'msrp': cols[idx_msrp] if idx_msrp is not None else None,
                'price': cols[idx_price] if idx_price is not None else None,
                'quantity': cols[idx_qty] if idx_qty is not None else None,
                'avail': cols[idx_avail] if idx_avail is not None else None,
                'orders_due': cols[idx_orders_due] if idx_orders_due is not None else None,
                'date_announced': cols[idx_announced] if idx_announced is not None else None,
                'date_expected': cols[idx_expected] if idx_expected is not None else None,
            }
            if data['item_number']:
                yield data


def update_inventory(auth):
    from intake.models import DistributorInventoryFile, DistributorInventoryLine, DistItem, Manufacturer
    username = auth.username
    password = auth.password
    distributor = auth.distributor

    session = get_hobbytyme_session(auth)
    if not session:
        print(f"Failed to login to Hobbytyme for {auth.partner}")
        return

    inventory_file = DistributorInventoryFile.objects.create(
        distributor=distributor,
        processed=True,
        update_date=timezone.now()
    )

    headers = DEFAULT_HEADERS.copy()

    # Get searchID for the full item list
    search_id = None
    try:
        search_page_url = "https://hobbytyme.com/dealers/index.cfm?action=products.search"
        response = session.get(search_page_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        search_id_input = soup.find('input', {'name': 'searchID'})
        if search_id_input:
            search_id = search_id_input.get('value')
    except Exception as e:
        print(f"Failed to get searchID: {e}")

    pages = []
    if search_id:
        pages.append(("All", "https://hobbytyme.com/dealers/index.cfm", {
            'action': 'products.search.save',
            'searchID': search_id,
            'available': '1',
            'itemsPerPage': '1000',
            'submit_btn': 'SEARCH'
        }))

    pages.extend([
        ("Just Arrived", "https://hobbytyme.com/dealers/index.cfm?action=products.justArrived"),
        ("Just Announced", "https://hobbytyme.com/dealers/index.cfm?action=products.justAnnounced"),
        ("Pre-Orders", "https://hobbytyme.com/dealers/index.cfm?action=products.preOrders"),
    ])

    collected_data = {}
    for page_info in pages:
        page_name = page_info[0]
        url = page_info[1]
        post_data = page_info[2] if len(page_info) > 2 else None
        print(f"Retrieving Hobbytyme page: {page_name}")
        for soup, current_url in fetch_hobbytyme_pages(session, url, headers, post_data=post_data):
            for data in scrape_hobbytyme_tables(soup):
                item_number = data['item_number']
                if item_number not in collected_data:
                    collected_data[item_number] = data
                else:
                    # Merge information from repeated items
                    existing = collected_data[item_number]
                    for key, value in data.items():
                        if value and not existing.get(key):
                            existing[key] = value

    for item_number, data in collected_data.items():
        quantity = None
        if data['quantity']:
            try:
                quantity_val = re.sub(r'[^\d.]', '', data['quantity'])
                if quantity_val:
                    quantity = int(float(quantity_val))
            except (ValueError, TypeError):
                pass

        in_stock = None
        if data.get('avail'):
            avail = data['avail'].lower()
            if avail =="in":
                in_stock = True
            elif avail=="out":
                in_stock = False
        if in_stock is None and quantity is not None:
            in_stock = quantity > 0

        msrp = None
        if data['msrp']:
            msrp_val = re.sub(r'[^\d.]', '', data['msrp'])
            if msrp_val:
                msrp = Decimal(msrp_val)

        dist_price = None
        if data['price']:
            dist_price_val = re.sub(r'[^\d.]', '', data['price'])
            if dist_price_val:
                dist_price = Decimal(dist_price_val)

        orders_due = None
        if data['orders_due']:
            try:
                orders_due = datetime.strptime(data['orders_due'], "%m/%d/%Y").date()
            except ValueError:
                pass

        announced = None
        if data['date_announced']:
            try:
                announced = datetime.strptime(data['date_announced'], "%m/%d/%Y").date()
            except ValueError:
                pass

        expected = None
        if data['date_expected']:
            try:
                expected = datetime.strptime(data['date_expected'], "%m/%d/%Y").date()
            except ValueError:
                pass

        mfc_name = data['manufacturer']
        manufacturer = None
        if mfc_name:
            manufacturer, _ = Manufacturer.objects.get_or_create(mfc_name=mfc_name)

        dist_item, created = DistItem.objects.get_or_create(
            distributor=distributor,
            dist_number=item_number,
            defaults={
                'dist_name': data['description'],
                'msrp': Money(msrp, 'USD') if msrp else None,
                'dist_price': Money(dist_price, 'USD') if dist_price else None,
                'orders_due': orders_due,
                'announced': announced,
                'expected': expected,
                'manufacturer': manufacturer,
                'in_stock': in_stock,
            }
        )
        if not created:
            if data['description']:
                dist_item.dist_name = data['description']
            if msrp:
                dist_item.msrp = Money(msrp, 'USD')
            if dist_price:
                dist_item.dist_price = Money(dist_price, 'USD')
            if orders_due:
                dist_item.orders_due = orders_due
            if announced:
                dist_item.announced = announced
            if expected:
                dist_item.expected = expected
            if manufacturer:
                dist_item.manufacturer = manufacturer
            if in_stock is not None:
                dist_item.in_stock = in_stock
            dist_item.save()
        dist_item.set_product_from_sku()

        # Add to file items
        inventory_file.items.add(dist_item)

        # Create historical line
        DistributorInventoryLine.objects.create(
            inventory_file=inventory_file,
            dist_item=dist_item,
            msrp=Money(msrp, 'USD') if msrp else None,
            dist_price=Money(dist_price, 'USD') if dist_price else None,
            orders_due=orders_due,
            announced=announced,
            expected=expected,
            quantity=quantity,
            in_stock=in_stock,
        )

    inventory_file.line_count = inventory_file.inventory_lines.count()
    inventory_file.save()
    return inventory_file
