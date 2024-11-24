import traceback

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from tqdm import tqdm

from checkout.models import Cart
from payments.models import Payment


class Command(BaseCommand):
    def handle(self, *args, **options):
        for payment in tqdm(Payment.objects.filter(collected=False), unit='payment'):
            cart = payment.cart.status
            payment_name = str(payment)
            original_cart_status = payment.cart.status
            payment.check_payment()
            if payment.collected:
                email = EmailMessage(f"Found uncollected payment for {cart.id}",
                                     f"""
Cart {cart.id} was originally {original_cart_status} and is now {cart.status}.
This was found while checking {payment_name}'s remote status.

{cart}
""",
                                     to=[settings.EMAIL_HOST_USER]
                                     )
                email.send()

