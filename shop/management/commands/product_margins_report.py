import csv
import datetime

from django.core.management.base import BaseCommand
from tqdm import tqdm

from openCGaT.management_util import email_report
from partner.models import Partner
from shop.models import InventoryItem


class Command(BaseCommand):
    help = "Generate a report of in-stock products with their prices, latest costs, and margins"

    def handle(self, *args, **options):
        partner = Partner.objects.get(name__icontains="Valhalla")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"reports/product_margins_{timestamp}.csv"
        
        with open(filename, "w", encoding="utf-8") as result_file:
            fieldnames = ["Publisher", "Game", "Product", "Barcode", "Current Price", "Latest Cost", "Margin ($)", "Margin (%)"]
            results_writer = csv.DictWriter(result_file, fieldnames=fieldnames)
            results_writer.writeheader()

            # Filter for in-stock inventory items for the partner
            inventory_items = InventoryItem.objects.filter(partner=partner, current_inventory__gt=0).select_related('product')

            for item in tqdm(inventory_items):
                product = item.product
                price = item.price
                
                # Get latest cost using the same logic as get_top_selling_items
                info = product.get_sold_info(partner)
                latest_cost = None
                if info["po_lines"].exists():
                    latest_purchase = info["po_lines"].exclude(cost_per_item__lte=0).first()
                    if latest_purchase:
                        latest_cost = latest_purchase.actual_cost

                margin_dollar = None
                margin_percent = None
                
                if latest_cost is not None and price is not None:
                    # Ensure same currency for subtraction if they are Money objects
                    try:
                        margin_dollar = price - latest_cost
                        if price.amount > 0:
                            margin_percent = (margin_dollar.amount / price.amount) * 100
                    except Exception as e:
                        self.stderr.write(f"Error calculating margin for {product}: {e}")

                data = {
                    "Publisher": product.publisher,
                    "Product": product.name,
                    "Barcode": product.barcode,
                    "Current Price": price,
                    "Latest Cost": latest_cost,
                    "Margin ($)": margin_dollar,
                    "Margin (%)": f"{margin_percent:.2f}%" if margin_percent is not None else "N/A",
                }
                if product.games:
                    data["Game"] = product.games.first()

                results_writer.writerow(data)

        email_report("Product Margins Report", [filename])
        self.stdout.write(self.style.SUCCESS(f"Report generated: {filename}"))
