import csv

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from tqdm import tqdm

from checkout.models import Cart


class Command(BaseCommand):
    def handle(self, *args, **options):
        filename = "reports/carts with discount codes.csv"
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['Email', 'Username', 'First order date', "First order was discounted", "First code",
                          'Number of orders',
                          'with discount codes', "without", ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for email in tqdm(Cart.submitted.values_list("email", flat=True).distinct(), unit=" Emails"):
                if email is None:
                    continue
                carts = Cart.submitted.filter(email=email)
                data = {"Email": email.strip()}
                data.update(get_data_from_carts(carts))
                writer.writerow(data)
            for owner in tqdm(User.objects.all(), unit=" Users"):
                carts = Cart.submitted.filter(owner=owner)
                if not carts.exists():
                    continue
                data = {"Email": owner.email.strip(), "Username": owner.username.strip()}
                data.update(get_data_from_carts(carts))
                writer.writerow(data)

        email = EmailMessage("User conversion and retention re discount codes",
                             "Attached is the report",
                             to=[settings.EMAIL_HOST_USER])
        email.attach_file(filename)
        email.send()
        print(f"Emailed to {settings.EMAIL_HOST_USER}")


def get_data_from_carts(carts):
    first_cart = carts.order_by('date_submitted').first()
    data = {
        "First order date": first_cart.date_submitted,
        "First order was discounted": first_cart.discount_code is not None,
        "First code": first_cart.discount_code,
        'Number of orders': carts.count(),
        'with discount codes': carts.filter(discount_code__isnull=False).count(),
        'without': carts.filter(discount_code__isnull=True).count(),
    }
    return data
