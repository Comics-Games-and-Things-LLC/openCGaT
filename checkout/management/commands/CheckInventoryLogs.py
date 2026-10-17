import csv
import traceback

import tqdm
from django.core.management.base import BaseCommand
from django.db.models import Q, Sum
from checkout.models import Cart
from openCGaT.management_util import email_report
from shop.models import Item, InventoryItem, InventoryLog

class Command(BaseCommand):
    help = "Confirms all submitted, paid, and completed carts's lines have an appropriate inventory log and subtract from inventory."

    def add_arguments(self, parser):
        parser.add_argument(
            '--correct',
            action='store_true',
            help='Rectify any missing lines',
        )

    def handle(self, *args, **options):
        correct = options['correct']
        csv_path = 'reports/inventory_logs_report.csv'

        # We specifically want SUBMITTED, PAID, and COMPLETED. 
        carts = Cart.objects.filter(status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED]).order_by('id')
        
        self.stdout.write(f"Checking {carts.count()} carts...")
        
        report_data = []
        missing_count = 0
        fixed_count = 0

        for cart in tqdm.tqdm(carts):
            try:
                cart_reason = f"Sold in cart {cart.id}"
                for line in cart.lines.all():
                    try:
                        if isinstance(line.item, InventoryItem):
                            # Check for an inventory log linked to this line
                            if InventoryLog.objects.filter(line=line).exists():
                                continue
                            
                            # Fallback: Check for an inventory log with the correct reason for this item
                            # This handles older data where the line foreign key was not consistently set.
                            if InventoryLog.objects.filter(item=line.item, reason=cart_reason).exists():
                                continue

                            self.stdout.write(self.style.WARNING(f"Cart {cart.id}, Line {line.id} ({line.item.product.name}) is missing inventory log"))
                            missing_count += 1

                            # Collect data for report
                            item = line.item
                            total_po = InventoryLog.objects.filter(item=item, po__isnull=False).aggregate(total=Sum('change_quantity'))['total'] or 0
                            total_sold = InventoryLog.objects.filter(item=item).filter(
                                Q(line__isnull=False) | Q(reason__icontains='Sold in cart')
                            ).aggregate(total=Sum('change_quantity'))['total'] or 0
                            
                            po_minus_sold = total_po + total_sold # total_sold is negative
                            diff = item.current_inventory - po_minus_sold
                            
                            emails = []
                            if cart.email:
                                emails.append(cart.email)
                            if cart.owner and cart.owner.email:
                                emails.append(cart.owner.email)
                            email_str = ", ".join(sorted(set(emails)))

                            report_data.append({
                                'date': cart.date_submitted or cart.date_created,
                                'cart': cart.id,
                                'product': item.product.name,
                                'quantity_sold': line.quantity,
                                'emails': email_str,
                                'current_quantity': item.current_inventory,
                                'qty_from_po_minus_qty_sold': po_minus_sold,
                                'difference': diff
                            })

                            if correct:
                                    try:
                                        # reduce_inventory calls adjust_inventory with quantity=-self.quantity
                                        # It also handles setting back_or_pre_order and is_preorder on the line.
                                        line.reduce_inventory()
                                        # Check again to confirm it worked (though adjust_inventory is atomic)
                                        if InventoryLog.objects.filter(line=line).exists():
                                            self.stdout.write(self.style.SUCCESS(f"  Line {line.id} inventory adjusted and logged."))
                                            fixed_count += 1
                                        else:
                                            self.stdout.write(self.style.ERROR(f"  Failed to adjust inventory for line {line.id}"))
                                    except Exception as e:
                                        self.stdout.write(self.style.ERROR(f"  Error correcting line {line.id}: {e}"))
                                        traceback.print_exc()
                    except Item.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f"Cart {cart.id}, Line {line.id} refers to a non-existent Item"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error processing cart {cart.id}: {e}"))
                traceback.print_exc()

        self.stdout.write(f"Finished. Total missing: {missing_count}")
        if correct:
            self.stdout.write(f"Total fixed: {fixed_count}")

        if csv_path:
            keys = ['date', 'cart', 'product', 'quantity_sold', 'emails', 'current_quantity', 'qty_from_po_minus_qty_sold', 'difference']
            with open(csv_path, 'w', newline='') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(report_data)
                output_file.flush()
                email_report("Inventory log errors on carts", [output_file.name])
            self.stdout.write(self.style.SUCCESS(f"Report saved to {csv_path}"))
