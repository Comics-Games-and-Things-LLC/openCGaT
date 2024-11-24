import csv

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management import BaseCommand
from tqdm import tqdm

from intake.models import PurchaseOrder


class Command(BaseCommand):
    help = "Find all purchase orders which are not complete"

    def handle(self, *args, **options):
        fieldnames = ["Distributor", "PO Number", "Date Invoiced", "Date Received",
                      "Empty", "Missing Costs", "Missing Quantities", "Total lines", "Cost does not match up"]

        total_po_count = PurchaseOrder.objects.count()
        completed_po_count = 0
        data = []
        for po in tqdm(PurchaseOrder.objects.order_by("date"), unit="po"):
            if po.completed:
                completed_po_count += 1
                continue
            row_data = {
                "Distributor": po.distributor,
                "PO Number": po.po_number,
                "Date Invoiced": po.date,
                "Date Received": po.date_received,
                "Total lines": po.lines.count()
            }
            if po.empty:
                row_data["Empty"] = True
            if po.missing_costs:
                row_data["Missing Costs"] = po.lines.filter(cost_per_item__isnull=True).count()
            if po.missing_quantities:
                row_data["Missing Quantities"] = po.lines.filter(expected_quantity=None).count() + po.lines.filter(
                    received_quantity=None).count()
            if po.cost_does_not_match_up:
                row_data["Cost does not match up"] = po.cost_does_not_match_up
            data.append(row_data)

        print(f"{completed_po_count}/{total_po_count} are complete")
        print(f"{total_po_count - completed_po_count}/{total_po_count} are not complete")

        filename = "reports/incomplete_purchase_orders.csv"
        with open(filename, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        print(f"Saved report to {filename}")
        pretty_name = "Incomplete purchase orders"

        if settings.DEBUG:
            pretty_name += "(Development)"
        email = EmailMessage(pretty_name, "Attached is the report", to=[settings.EMAIL_HOST_USER])
        email.attach_file(filename)
        email.send()
        print(f"Emailed to {settings.EMAIL_HOST_USER}")
