import csv
import datetime

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from checkout.models import Cart


class Command(BaseCommand):
    def handle(self, *args, **options):
        from checkout.models import CheckoutLine
        from shop.models import Product
        product = Product.objects.get(name="Warhammer 40000: Armageddon")
        for line in CheckoutLine.objects.filter(cart__status=Cart.OPEN, item__product=product):
            print("Removing line: ", line)
            line.delete()