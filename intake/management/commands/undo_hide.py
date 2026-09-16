import os
import re
import glob
from django.core.management.base import BaseCommand
from shop.models import Product

class Command(BaseCommand):
    help = 'Unmark products hidden based on the latest hidden products.txt file from the reports directory'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Specific report file to use')

    def handle(self, *args, **options):
        report_file = options.get('file')
        
        if report_file:
            if not os.path.exists(report_file):
                self.stdout.write(self.style.ERROR(f"File not found: {report_file}"))
                return
        else:
            # Find all hidden_products_*.txt files in reports/
            report_files = glob.glob('reports/hidden_products_*.txt')
            
            if not report_files:
                self.stdout.write(self.style.ERROR("No hidden_products_*.txt files found in reports/"))
                return

            # Get the latest file by name (since they have timestamps in names)
            # Alphabetical sort on timestamps works correctly for these filenames.
            report_file = max(report_files)
        
        self.stdout.write(f"Reading from report file: {report_file}")
        
        # Pattern to match both GW and generic hide logs:
        # 1. Hid {product_name}, which we had {count}
        # 2. Hid {product_name}, since there was no stock
        pattern = re.compile(r"^Hid (.*), (?:since there was no stock|which we had .*)$")
        
        unhidden_count = 0
        not_found_count = 0
        already_visible_count = 0
        
        with open(report_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                match = pattern.match(line)
                if match:
                    product_name = match.group(1)
                    try:
                        product = Product.objects.get(name=product_name)
                        if product.page_is_draft:
                            product.page_is_draft = False
                            # Before saving, ensure it has a release date if that's required to stay non-draft
                            if not product.release_date:
                                self.stdout.write(self.style.WARNING(f"Product '{product_name}' has no release date, setting to draft might persist."))
                            product.save()
                            self.stdout.write(f"Unhid: {product_name}")
                            unhidden_count += 1
                        else:
                            self.stdout.write(f"Product already visible: {product_name}")
                            already_visible_count += 1
                    except Product.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Product not found: {product_name}"))
                        not_found_count += 1
                    except Product.MultipleObjectsReturned:
                        # Should not happen due to unique constraint but good to handle
                        self.stdout.write(self.style.ERROR(f"Multiple products found for: {product_name}"))
                        not_found_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f"Could not parse line: {line}"))

        self.stdout.write(self.style.SUCCESS(
            f"Finished. Unhidden {unhidden_count} products. "
            f"{already_visible_count} already visible. "
            f"{not_found_count} failures."
        ))
