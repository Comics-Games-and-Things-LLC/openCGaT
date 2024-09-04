import csv

from django.core.management.base import BaseCommand
from django.db.models import Sum
from tqdm import tqdm

from checkout.models import Cart
from partner.models import Partner
from shop.models import Product


class Command(BaseCommand):
    # Known bug: If a product is under multiple games, it will mark it as sold by the first game, and then not be
    # available to check for the second game. One way of solving this would be to reset the "sold" count between games.

    def add_arguments(self, parser):
        pass
        # parser.add_argument("--year", type=int)
        # parser.add_argument("--all", type=bool)

    def handle(self, *args, **options):

        partner = Partner.objects.get(name__icontains="Valhalla")

        result_file = open(f"reports/sales_by_item.csv", "w", encoding="utf-8")
        results_writer = csv.DictWriter(result_file,
                                        ["Publisher", "Game", "Product",
                                         "Sold (Total)", "Sold After Release",
                                         "Latest Cost"])
        results_writer.writeheader()

        for product in tqdm(Product.objects.filter(page_is_draft=False, release_date__isnull=False)):

            info = product.get_sold_info(partner)
            after_release_sales = info['sales'] \
                .filter(cart__date_submitted__gt=product.release_date) \
                .filter(cart__status__in=[Cart.SUBMITTED, Cart.PAID, Cart.COMPLETED]).exclude(
                cancelled=True).aggregate(sum=Sum("quantity"))['sum']

            # Things to add to this report:
            # turnover

            data = {
                "Publisher": product.publisher,
                "Product": product.name,
                "Sold (Total)": info["x_sold"],
                "Sold After Release": after_release_sales,
            }
            if product.games:
                data["Game"] = product.games.first()  # Use first game if we have more than one.

            if info["po_lines"].exists():
                cost = info["po_lines"].exclude(cost_per_item__lte=0).first()
                data["Latest Cost"] = cost

            results_writer.writerow(data)

        result_file.close()
        print("Done")
