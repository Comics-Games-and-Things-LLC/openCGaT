from datetime import timedelta

import requests
from django.db import models
from django.utils import timezone

from intake.distributors.games_workshop import find_barcode_from_article
from intake.models import PurchaseOrder, PoShipment

NSHIFT_COUNT_URL = "https://internal-api.nshiftportal.com/track/.pa/shipmentdata/reporting/publicSearch/count"
NSHIFT_ITEMS_URL = "https://internal-api.nshiftportal.com/track/.pa/shipmentdata/reporting/publicSearch/items"
NSHIFT_SHIPMENT_URL = "https://internal-api.nshiftportal.com/track/.pa/shipmentdata/operational/shipments/{}/aggregated"
PUBLIC_PROFILE_ID = "fb09731e-775b-40d4-9e42-c8feab8299e0"

CARRIER_LINKS = {
    'UPS Ground': 'https://www.ups.com/track?tracknum={}',
    'USPS Priority Mail': 'https://tools.usps.com/go/TrackConfirmAction?tLabels={}',
    'USPS Ground Advantage': 'https://tools.usps.com/go/TrackConfirmAction?tLabels={}',
}


def fetch_nshift_data(invoice_id):
    payload = {
        "publicProfileId": PUBLIC_PROFILE_ID,
        "query": invoice_id,
    }

    try:
        # First, check the count
        response = requests.post(NSHIFT_COUNT_URL, json=payload, timeout=10)
        response.raise_for_status()
        total_count = int(response.text)

        if total_count == 0:
            return []

        page_size = 20
        all_items = []
        num_pages = (total_count + page_size - 1) // page_size

        for page_index in range(num_pages):
            item_payload = payload.copy()
            item_payload.update({
                "pageIndex": page_index,
                "pageSize": page_size
            })

            response = requests.post(NSHIFT_ITEMS_URL, json=item_payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            all_items.extend(data)

        return all_items
    except Exception as e:
        print(f"Error fetching nShift data for {invoice_id}: {e}")
        return []


def fetch_detailed_shipment_data(shipment_uuid, timestamp):
    params = {
        "date": timestamp,
        "profile": PUBLIC_PROFILE_ID,
    }
    try:
        response = requests.get(NSHIFT_SHIPMENT_URL.format(shipment_uuid), params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching detailed nShift shipment data for {shipment_uuid}: {e}")
        return None


def update_tracking_from_nshift():
    # For any GW purchase order starting with M
    # Only try every 24 hours
    check_threshold = timezone.now() - timedelta(hours=24)
    gw_pos = PurchaseOrder.objects.filter(
        distributor__dist_name="Games Workshop",
        po_number__startswith="M"
    ).filter(
        models.Q(last_nshift_check__isnull=True) | models.Q(last_nshift_check__lt=check_threshold)
    )

    for po in gw_pos:
        # Skip anything that already has a shipment, assume that more won't be added after the first check.
        if po.shipments.exists():
            continue

        po.last_nshift_check = timezone.now()
        po.save()

        nshift_data = fetch_nshift_data(po.po_number)
        if not nshift_data:
            continue

        process_nshift_data(nshift_data, po)


def process_nshift_data(data, po):
    from intake.models import PoShipmentLine
    from djmoney.money import Money

    for shipment_data in data:
        sender_ref = shipment_data.get('senderReference')
        if not sender_ref:
            continue
        tracking_number = shipment_data.get('shipmentNumber')
        carrier = shipment_data.get('product')
        shipment_uuid = shipment_data.get('uuid')
        submit_date = shipment_data.get('submitDate')

        if tracking_number:
            shipment, created = PoShipment.objects.get_or_create(
                po=po,
                tracking_number=tracking_number
            )
            shipment.carrier = carrier
            shipment.nshift_uuid = shipment_uuid
            if carrier in CARRIER_LINKS:
                shipment.carrier_link = CARRIER_LINKS[carrier].format(tracking_number)
            shipment.save()

            if shipment_uuid and submit_date:
                detailed_data = fetch_detailed_shipment_data(shipment_uuid, submit_date)
                if detailed_data:
                    process_detailed_shipment_data(detailed_data, shipment)

    # After processing all shipments, update POLines
    shipment_lines = PoShipmentLine.objects.filter(shipment__po=po)
    if shipment_lines.exists():
        print("Updating lines from shipment data")

        # Get the list of all POLines that are null before searching/updating any of them
        # "and allow those lines to be updated even if they are not null at apply time"
        # I'll keep track of which POLines were originally null.
        null_po_lines = list(po.lines.filter(cost_per_item__isnull=True))
        originally_null_ids = [l.id for l in null_po_lines]

        for s_line in shipment_lines:
            barcode = find_barcode_from_article(s_line.sku)
            if not barcode:
                continue

            # Find a POLine to update. 
            # Requirement: "attempt to find the POLine... and setting the expected quantity and cost per item if they are not yet set."
            # "Since multiple POShipmentLines may match one POLine, get the list of all POLines that are null before searching/updating"

            matching_lines = po.lines.filter(barcode=barcode)
            for po_line in matching_lines:
                # Update if it was originally null or is currently null
                if po_line.id in originally_null_ids or (
                        po_line.expected_quantity is None and po_line.cost_per_item is None):
                    if s_line.quantity:
                        po_line.expected_quantity = s_line.quantity
                    if s_line.unit_value:
                        po_line.cost_per_item = Money(s_line.unit_value, 'USD')
                    po_line.save()
                # Don't expect more than one PO line
                break


def process_detailed_shipment_data(detailed_data, shipment):
    from intake.models import PoShipmentLine
    shipment_obj = detailed_data.get('shipment', {})
    detail_groups = shipment_obj.get('detailGroups', [])

    article_info_group = next((group for group in detail_groups if group.get('name') == 'Article Info'), None)
    if not article_info_group:
        return

    for row in article_info_group.get('rows', []):
        line_number = row.get('number')
        # lineNumber in row seems to be always 1 in example, but number varies.
        # Requirement: "number (saved as line number)"

        details = row.get('details', [])
        line_data = {
            'shipment': shipment,
            'line_number': line_number,
        }

        for detail in details:
            name = detail.get('name')
            value = detail.get('value')
            if name == 'No units':
                try:
                    line_data['quantity'] = int(value)
                except (ValueError, TypeError):
                    pass
            elif name == 'Unit of Measure (code)':
                line_data['unit_of_measure'] = value
            elif name == 'Description of goods':
                line_data['description'] = value
            elif name == 'Unit Value':
                try:
                    line_data['unit_value'] = value
                except (ValueError, TypeError):
                    pass
            elif name == 'Article No':
                line_data['sku'] = value

        # Use update_or_create to avoid duplicates if re-processed
        PoShipmentLine.objects.update_or_create(
            shipment=shipment,
            line_number=line_number,
            sku=line_data.get('sku'),
            defaults=line_data
        )
