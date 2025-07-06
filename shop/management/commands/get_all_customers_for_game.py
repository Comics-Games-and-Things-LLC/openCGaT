from django.core.management.base import BaseCommand

from checkout.models import CheckoutLine
from game_info.models import Game
from partner.models import Partner


class Command(BaseCommand):
    pass

    def handle(self, *args, **options):
        partner = Partner.objects.get(name__icontains="Valhalla")
        game = Game.objects.get(name="Warhammer: The Horus Heresy")
        print(game)

        customers_with_accounts = CheckoutLine.objects.filter(item__product__games=game).exclude(
            cart__owner__isnull=True).order_by('cart__owner').values_list(
            'cart__owner__email', flat=True).distinct()

        print("With accounts count: " , customers_with_accounts.count())

        customers_as_guest = CheckoutLine.objects.filter(item__product__games=game).exclude(
            cart__email__isnull=True).order_by('cart__email').values_list(
            'cart__email', flat=True).distinct()

        print("As guest count: " , customers_as_guest.count())

        # Converting to dict makes distinct
        all_customers = list(dict.fromkeys((set(customers_with_accounts) | set(customers_as_guest))))

        print("All count: " , len(all_customers))

        print(",".join(customers_with_accounts))
