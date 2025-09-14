from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from checkout.models import Cart
from digitalitems.models import DIFile, DigitalItem


class Command(BaseCommand):

    def handle(self, *args, **options):
        carts = Cart.objects.filter(status__in=[Cart.PAID, Cart.COMPLETED]).order_by('date_paid')
        for cart in carts:
            print(cart)
            for line in cart.lines.all():
                if isinstance(line.item, DigitalItem):
                    try:
                        line.item.downloads.create(user=cart.owner, date=cart.date_paid, added_from_cart=cart)
                    except Exception as e:
                        print(e)
