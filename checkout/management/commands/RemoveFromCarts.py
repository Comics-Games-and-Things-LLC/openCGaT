from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        from checkout.models import CheckoutLine, Cart
        from shop.models import Product
        product = Product.objects.get(name="Warhammer 40000: Armageddon")
        for line in CheckoutLine.objects.filter(cart__status__in=[Cart.FROZEN, Cart.OPEN], item__product=product):
            line.cart.thaw()
            line.cart.save()
            line.delete()
            print("Removing line: ", line)
            line.delete()
