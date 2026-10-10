import csv
from django.core.management.base import BaseCommand
from shop.models import Product

class Command(BaseCommand):
    help = 'Export Games Workshop products with a publisher SKU'

    def handle(self, *args, **options):
        # Filter for products where publisher name is "Games Workshop"
        # and publisher_sku is not null or empty.
        products = Product.objects.filter(
            publisher__name="Games Workshop",
            publisher_sku__isnull=False
        ).exclude(publisher_sku="")

        filename = 'reports/gw_products_export.csv'
        fieldnames = [
            'name',
            'faction(s)',
            'category(ies)',
            'preorder_date', 
            'release_date', 
            'msrp', 
            'publisher_sku', 
            'publisher_short_sku'
        ]

        count = 0
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for product in products:
                writer.writerow({
                    'name': product.name,
                    'faction(s)': ", ".join(product.factions.values_list("name", flat=True)),
                    'category(ies)': ", ".join(product.categories.values_list("name", flat=True)),
                    'preorder_date': product.preorder_or_secondary_release_date,
                    'release_date': product.release_date,
                    'msrp': product.msrp.amount if product.msrp else None,
                    'publisher_sku': product.publisher_sku,
                    'publisher_short_sku': product.publisher_short_sku,
                })
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully exported {count} products to {filename}'))
