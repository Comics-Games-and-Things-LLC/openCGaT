import traceback

from django.core.management.base import BaseCommand

from checkout.models import Cart


class Command(BaseCommand):
    def handle(self, *args, **options):
        for cart in Cart.objects.filter(status__in=[Cart.SUBMITTED, Cart.PROCESSING, Cart.FROZEN]).order_by('id'):
            if cart.is_processing:  # Resubmit processing carts, as they could be in-store pickup.
                cart.submit()
            if cart.stripepaymentintent_set.exists():
                print("{}: {}".format(cart.id, cart))
                try:
                    for intent in cart.stripepaymentintent_set.all():
                        print(intent)
                        intent.captured = False
                        intent.save()  # Reset status of all payment intents that haven't actually through.
                        intent.try_mark_captured()  # Check to see if they now have correct data
                except Exception as e:
                    print(e)
                    traceback.print_exc()
            if cart.payments.exists():
                cart.total_paid = 0
                cart.save()
                print("{}: {}".format(cart.id, cart))
                try:
                    for payment in cart.payments.all():
                        if payment.collected:
                            print(payment)
                            print("Reapplying to cart")
                            payment.applied_to_cart = False
                            payment.save()
                            payment.apply_to_cart()
                        else:
                            print(payment)
                            print("Checking remote status")
                            if hasattr(payment, 'check_payment'):
                                payment.check_payment()
                except Exception as e:
                    print(e)
                    traceback.print_exc()
