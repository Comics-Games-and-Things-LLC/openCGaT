from django.core.management.base import BaseCommand

from checkout.models import StripePaymentIntent


class Command(BaseCommand):
    def handle(self, *args, **options):
        for intent in StripePaymentIntent.objects.filter(amount_to_pay_currency="XYZ"):
            intent.amount_to_pay_currency = 'USD'
            intent.save()
