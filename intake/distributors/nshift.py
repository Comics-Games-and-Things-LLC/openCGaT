import json
import requests
from django.db import models
from django.utils import timezone
from datetime import timedelta
from intake.models import PurchaseOrder, PoShipment

NSHIFT_COUNT_URL = "https://internal-api.nshiftportal.com/track/.pa/shipmentdata/reporting/publicSearch/count"
NSHIFT_ITEMS_URL = "https://internal-api.nshiftportal.com/track/.pa/shipmentdata/reporting/publicSearch/items"
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
    for shipment_data in data:
        sender_ref = shipment_data.get('senderReference')
        if not sender_ref:
            continue
        tracking_number = shipment_data.get('shipmentNumber')
        carrier = shipment_data.get('product')
        if tracking_number:
            shipment, created = PoShipment.objects.get_or_create(
                po=po,
                tracking_number=tracking_number
            )
            shipment.carrier = carrier
            if carrier in CARRIER_LINKS:
                shipment.carrier_link = CARRIER_LINKS[carrier].format(tracking_number)
            shipment.save()

