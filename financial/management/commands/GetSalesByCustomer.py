import csv

from django.core.management.base import BaseCommand
from tqdm import tqdm

from checkout.models import Cart, StripeCustomerId


class Command(BaseCommand):
    def handle(self, *args, **options):
        year = 2023
        fieldnames = ['Customer', 'Email', 'Stripe Customer ID', 'Total Purchases']

        customers = {}

        for cart in tqdm(Cart.submitted.filter(status__in=[Cart.PAID, Cart.COMPLETED], date_paid__year=year)
                                 .order_by("date_paid")):
            # Step 1: identify customer.
            customer = get_customer_for_cart(cart)

            subtotal = cart.get_subtotal_after_cancellations()  # Should exclude non-valhalla customers, I think.

            # Step 2: Add customer's total to the list
            if subtotal.amount == 0:
                continue  # Skip this

            print(f"Adding {subtotal} to {customer}")
            if customer not in customers:
                customers[customer] = subtotal
            else:
                customers[customer] += subtotal

        with open('reports/Sales_by_customer_{}.csv'.format(year), 'w',
                  newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for customer in tqdm(customers.keys()):
                print(f"{customer} purchased {customers[customer]}")
                name = customer
                email = customer
                if hasattr(customer, 'name'):
                    name = customer.name
                if hasattr(customer, 'email'):
                    email = customer.email
                writer.writerow({
                    'Customer': name,
                    'Email': email,
                    'Total Purchases': customers[customer]
                })


def get_customer_for_cart(cart):
    # Check for an owner
    if cart.owner:
        return cart.owner
    # TODO: Check if they made an account later with the same email

    # Check if they bought some stuff with a card they use with an account.
    # As far as I can tell, there's no way to pull the "guest" customer created by stripe,
    # so this does nothing right now. Line that would slow things down a lot commented out.
    stripe_id = None
    if cart.at_pos and cart.stripepaymentintent_set.exists():
        for in_store_PI in cart.stripepaymentintent_set.all():
            pi_json = {}  # in_store_PI.get_json()
            if pi_json and pi_json["customer"]:
                stripe_id = pi_json["customer"]
    if stripe_id:
        if StripeCustomerId.objects.filter(id=stripe_id).exists():
            return StripeCustomerId.objects.get(id=stripe_id).user
        return stripe_id
    return f"Unknown, Cart {cart.id}"
