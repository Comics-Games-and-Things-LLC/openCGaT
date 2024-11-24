import base64
import datetime

import requests
import stripe
from django.conf import settings
from django.core import mail
from django.db import models, transaction
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from polymorphic.models import PolymorphicModel

from checkout.models import Cart


class Payment(PolymorphicModel):
    cart = models.ForeignKey('checkout.Cart', on_delete=models.PROTECT, related_name="payments")
    requested_payment = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    processing_fees = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', blank=True, null=True)

    collected_timestamp = models.DateTimeField(null=True, blank=True)
    collected = models.BooleanField(default=False)

    cancelled_timestamp = models.DateTimeField(null=True, blank=True)
    cancelled = models.BooleanField(default=False)

    applied_to_cart = models.BooleanField(default=False)

    def __str__(self):
        text = "Payment ({}) for {} from cart {}".format(self.id, self.requested_payment, self.cart_id)
        if self.collected:
            text = f"Collected {text}"
        if self.cancelled:
            text = f"Cancelled {text}"
        return text

    @property
    def amount_cents(self):
        amount = self.requested_payment.amount
        amount_cents = int(amount * 100)
        return amount_cents

    def get_status(self):
        if self.collected:
            return "Collected"
        if self.cancelled:
            return "Cancelled"
        if self.applied_to_cart:
            return "Collected and Applied"

    def get_summary(self):
        result = {"requested_amount": str(self.requested_payment),
                  "status": self.get_status()
                  }
        try:
            result.update(self.get_remote_status())
        except stripe.error.InvalidRequestError:
            result["remote_status"] = "Could not properly read payment intent"
        return result

    def apply_to_cart(self):
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=self.id)
            if payment.collected and not payment.applied_to_cart:
                payment.cart.mark_processing()  # Mark processing just in case the cart rolls back.
                # pay_amount has its own atomic lock and submit.
                success = payment.cart.pay_amount(self.requested_payment)
                if success:
                    payment.applied_to_cart = True
                    payment.save()

    def mark_collected(self, timestamp=None):
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=self.id)
            if not payment.collected:
                if timestamp:
                    payment.collected_timestamp = timestamp
                else:
                    payment.collected_timestamp = datetime.datetime.now()
                payment.collected = True
                payment.save()

    def mark_cancelled(self, timestamp=None):
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=self.id)
            if not payment.cancelled:
                if timestamp:
                    payment.cancelled_timestamp = timestamp
                else:
                    payment.cancelled_timestamp = datetime.datetime.now()
                payment.cancelled = True
                payment.save()

    def get_remote_status(self):
        """
        Calls to payment processor, checks collected and cancelled status
        """
        return {}

    def get_refunded_amount(self):
        return Money(0, "USD")


class CashPayment(Payment):
    pass


class StripePayment(Payment):
    """
    Stripe payments use a payment intent ID to handle a transaction
    """
    intent_id = models.CharField(max_length=50, unique=True)

    def __str__(self):
        name = "Stripe Payment Intent {} for cart {}, {} cents".format(self.intent_id, self.cart_id, self.amount_cents)
        if self.collected:
            name += ", captured"
        return name

    def check_payment(self):
        if not self.collected and not self.cancelled:
            intent = stripe.PaymentIntent.retrieve(self.intent_id)
            if intent.amount_received > 0:
                if not (intent.amount_received + 1 >= self.amount_cents >= intent.amount_received - 1):
                    mail.mail_admins("Cart {} has mismatched collected amount!".format(self.cart_id),
                                     fail_silently=True,
                                     message="You may need to send a refund! Check stripe and this cart ID. \n"
                                             "The system thinks this payment intent is supposed to have connected {} "
                                             "cents".format(
                                         self.amount_cents) +
                                             " and stripe collected {}".format(intent.amount)
                                     )
                timestamp = intent.charges.data[0].created
                self.mark_collected(datetime.datetime.fromtimestamp(timestamp))
                self.apply_to_cart()

    @staticmethod
    def update_remote_intent(intent_id, cart):
        amount = cart.final_total.amount
        amount_cents = int(amount * 100)
        intent = stripe.PaymentIntent.retrieve(str(intent_id))
        if intent.amount != amount_cents:
            intent.modify(intent.id, amount=amount_cents)

    def update_intent(self):
        StripePayment.update_remote_intent(self.intent_id, self.cart)
        if self.requested_payment != self.cart.final_total:
            self.requested_payment = self.cart.final_total
        self.save()

    @staticmethod
    def generate_stripe_pi(cart):
        """
        Internal method for use only by get_create_or_update
        :param cart:
        :return:
        """
        final_total = cart.final_total
        amount = final_total.amount
        amount_cents = int(amount * 100)

        # check for checkout v1 payment intents:
        old_pis = cart.stripepaymentintent_set.filter(cancelled=False)
        if old_pis.count() > 1:
            for intent_db in old_pis:
                intent_db.cancel()
        if old_pis.count() == 1:
            intent_id = old_pis.first().id
            StripePayment.update_remote_intent(intent_id, cart)
        else:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',
                automatic_payment_methods={"enabled": True},
                description="CG&T Cart Number: " + str(cart.id)
            )
            intent_id = intent.id
        return StripePayment.objects.create(cart=cart, intent_id=intent_id, requested_payment=final_total)

    @staticmethod
    def get_create_or_update_intent_for_cart(cart):
        existing_payments = StripePayment.objects.filter(cart=cart)
        if existing_payments.count() > 1:
            for intent_db in existing_payments:
                intent_db.remote_cancel()
        if existing_payments.count() == 1:
            existing_payment = existing_payments.first()
            existing_payment.update_intent()
            existing_payment.check_payment()
            return existing_payments.first()

        # No existing intent, make a new one:
        return StripePayment.generate_stripe_pi(cart)

    def get_client_secret(self):
        intent = stripe.PaymentIntent.retrieve(self.intent_id)
        return {
            'clientSecret': intent['client_secret'],
            'publishableAPIKey': settings.STRIPE_PUBLIC_KEY,
        }

    def remote_cancel(self):
        pi = stripe.PaymentIntent.retrieve(self.intent_id)
        pi.cancel()
        self.mark_cancelled()

    def get_remote_json(self):
        pi = stripe.PaymentIntent.retrieve(self.intent_id)
        print(pi)
        return pi

    def get_remote_status(self):
        pi = stripe.PaymentIntent.retrieve(self.intent_id)
        return {
            "platform": "Stripe",
            "Remote ID": self.intent_id,
            "remote_status": pi.status,
            "amount_requested": "$" + str(pi.amount / 100),
            "amount_collected": "$" + str(pi.amount_received / 100),
        }

    def get_refunded_amount(self):
        amount = Money(0, "USD")
        for refund in stripe.Refund.list(payment_intent=self.intent_id):
            amount += Money(refund.amount / 100, "USD")
        return amount


class PaypalPayment(Payment):
    """
    Paypal payments
    """
    order_id = models.CharField(max_length=50, unique=True, null=True)
    payment_id = models.CharField(max_length=50, null=True)

    @property
    def reference_id(self):
        return self.id

    @property
    def invoice_id(self):
        return "{}-{}".format(self.cart_id, self.id)

    @staticmethod
    def send_post(request_endpoint, data=None):
        return requests.post(
            "{}/{}".format(settings.PAYPAL_ENDPOINT, request_endpoint),
            json=data,
            headers={
                "Authorization": "Bearer {}".format(PaypalPayment.generate_access_token()),
                "Content-Type": "application/json",
            },
            timeout=(7, 30)
        )

    @staticmethod
    def get_request(request_endpoint, data=None):
        return requests.get(
            "{}/{}".format(settings.PAYPAL_ENDPOINT, request_endpoint),
            json=data,
            headers={
                "Authorization": "Bearer {}".format(PaypalPayment.generate_access_token()),
                "Content-Type": "application/json",
            },
            timeout=(7, 30)
        )

    def prepare_shipping_data(self):
        data = {}
        if self.cart.delivery_method == Cart.PICKUP_ALL:
            pass  # data = {"type": "PICKUP_IN_PERSON"} # SHIPPING_TYPE_NOT_SUPPORTED_FOR_CLIENT
        elif self.cart.delivery_method == Cart.SHIP_ALL:
            data = {
                "type": "SHIPPING",
                "address": {
                    "address_line_1": self.cart.shipping_address.line1,
                    "address_line_2": self.cart.shipping_address.line2,
                    "admin_area_1": self.cart.shipping_address.state,
                    "admin_area_2": self.cart.shipping_address.line4,
                    "postal_code": self.cart.shipping_address.postcode,
                    "country_code": self.cart.shipping_address.country.code,
                }
            }
        return data

    def prepare_order_purchase_units_data(self):
        shipping_data = self.prepare_shipping_data()
        return [{
            "amount": {
                "currency_code": "USD",
                "value": str(round(self.requested_payment.amount, 2)),
            },
            "reference_id": self.reference_id,
            "invoice_id": self.invoice_id,
            'shipping': shipping_data
        }]

    def generate_paypal_order(self):
        data = {
            "intent": "CAPTURE",
            "purchase_units": self.prepare_order_purchase_units_data()
        }
        response = self.send_post("v2/checkout/orders", data)
        result = response.json()
        print(result)
        self.order_id = result['id']
        self.save()
        return result

    def update_order(self):
        data = [{"op": "replace",
                 "path": "purchase_units",
                 "value": self.prepare_order_purchase_units_data()}]
        response = self.send_post("v2/checkout/orders/{}".format(self.order_id), data)
        print(response.status_code)
        if response.status_code == 204:
            self.requested_payment = self.cart.final_total
            self.save()
        return response.json()

    def get_remote_json(self):
        response = self.get_request("v2/checkout/orders/{}".format(self.order_id))
        return response.json()

    def get_or_make_order(self):
        if self.order_id:
            if self.requested_payment != self.cart.final_total:
                self.update_order()
            return self.check_status_and_mark_paid()
        else:
            return self.generate_paypal_order()

    @staticmethod
    def generate_access_token():
        auth_string = settings.PAYPAL_CLIENT_ID + ":" + settings.PAYPAL_SECRET
        auth_bytes_string = base64.b64encode(auth_string.encode()).decode()

        response = requests.post(
            "{}/v1/oauth2/token".format(settings.PAYPAL_ENDPOINT),
            data="grant_type=client_credentials",
            headers={
                "Authorization": "Basic {}".format(auth_bytes_string),
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

        return response.json()['access_token']

    @staticmethod
    def generate_client_token():
        response = requests.post(
            "{}/v1/identity/generate-token".format(settings.PAYPAL_ENDPOINT),
            headers={
                "Authorization": "Bearer {}".format(PaypalPayment.generate_access_token()),
                "Accept-Language": "en_US",
                "Content-Type": "application/json",
            }
        )
        return response.json()['client_token']

    def check_status_and_mark_paid(self):
        """
        :returns: Data from PayPal API to be used by frontend
        """
        response = self.send_post("v2/checkout/orders/{}/capture".format(self.order_id))
        print(response.status_code)
        response_data = response.json()
        print(response_data)
        try:
            if response.status_code == 201 or (
                    response.status_code == 200 and response_data['status'] == 'COMPLETED'
            ):
                self.payment_id = response_data['purchase_units'][0]['payments']['captures'][0]["id"]
                self.mark_collected()
                self.refresh_from_db()
                self.apply_to_cart()
        except Exception as e:
            print(e)
        return response_data

    def get_remote_status(self):
        print(self.order_id)
        response = self.get_request("v2/checkout/orders/{}".format(self.order_id))
        print(response.status_code)
        if response.status_code not in [200, 201]:
            return {
                "platform": "Paypal",
                "remote_id": self.order_id,
                "remote_status": response.status_code
            }
        response_data = response.json()
        print(response_data)
        remote_status, amount_collected, amount_requested = None, None, None
        try:
            remote_status = response_data['status']
            amount_requested = "$" + response_data['purchase_units'][0]['amount']['value']
        except KeyError:
            pass
        return {
            "platform": "Paypal",
            "remote_id": self.order_id,
            "remote_status": remote_status,
            "amount_requested": amount_collected,
            "amount_collected": amount_requested,
        }

    def get_refunded_amount(self):
        amount = Money(0, "USD")
        if not self.payment_id:
            return amount

        response = self.get_request("v2/payments/authorizations/{}".format(self.payment_id))
        refund_id = None
        return amount
