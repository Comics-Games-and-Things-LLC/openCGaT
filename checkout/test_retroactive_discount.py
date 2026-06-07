from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from djmoney.money import Money
from checkout.models import Cart, CheckoutLine
from partner.models import Partner
from shop.models import Product, InventoryItem
from discount_codes.models import DiscountCode, PartnerDiscount
from django.contrib.sites.models import Site

class RetroactiveDiscountTest(TestCase):
    def setUp(self):
        self.site, _ = Site.objects.get_or_create(domain="example.com", name="example.com")
        self.user = User.objects.create_user(username='testuser', password='password')
        self.partner = Partner.objects.create(name="Test Partner", slug="test-partner")
        self.partner.administrators.add(self.user)
        
        self.product = Product.objects.create(name="Test Product")
        self.item = InventoryItem.objects.create(
            product=self.product, 
            partner=self.partner, 
            price=Money(100, "USD"),
            default_price=Money(100, "USD")
        )
        
        self.code = DiscountCode.objects.create(code="SAVE20")
        self.partner_discount = PartnerDiscount.objects.create(
            code=self.code,
            partner=self.partner,
            discount_percentage=20,
            referrer_kickback=0
        )
        
        self.cart = Cart.objects.create(site=self.site, status=Cart.OPEN)
        self.cart.add_item(self.item)
        self.cart.submit() # This should set lines_submitted
        self.cart.update_final_totals()

    def test_retroactive_discount(self):
        self.client.login(username='testuser', password='password')
        
        # Verify initial state
        self.assertEqual(self.cart.final_total, Money(100, "USD"))
        line = self.cart.lines_submitted.first()
        self.assertEqual(line.price_per_unit_at_submit, Money(100, "USD"))
        self.assertIsNone(line.price_per_unit_override)
        
        url = reverse('partner_retroactively_apply_discount_with_code', kwargs={
            'partner_slug': self.partner.slug,
            'cart_id': self.cart.id,
            'discount_code': self.code.code
        })
        
        response = self.client.get(url)
        
        # Check redirect
        self.assertEqual(response.status_code, 302)
        
        # Refresh from DB
        self.cart.refresh_from_db()
        line.refresh_from_db()
        
        # Verify discount applied
        self.assertEqual(line.price_per_unit_at_submit, Money(80, "USD"))
        self.assertEqual(line.price_per_unit_override, Money(100, "USD"))
        self.assertEqual(self.cart.discount_code, self.code)
        
        # Verify cart totals
        # After update_final_totals, final_total should be 80
        # initial was 100, so refund should be 20
        self.assertEqual(self.cart.final_total, Money(80, "USD"))
        self.assertEqual(self.cart.amount_refunded, Money(20, "USD"))
        
        # Verify private comments
        self.assertIn(f"Discount code {self.code.code} retroactively applied, to refund amount", self.cart.private_comments)
        self.assertIn("20.00", self.cart.private_comments)

    def test_retroactive_discount_query_param(self):
        self.client.login(username='testuser', password='password')
        
        url = reverse('partner_retroactively_apply_discount', kwargs={
            'partner_slug': self.partner.slug,
            'cart_id': self.cart.id,
        })
        
        response = self.client.get(url, {'discount_code': self.code.code})
        
        # Check redirect
        self.assertEqual(response.status_code, 302)
        
        # Refresh from DB
        self.cart.refresh_from_db()
        
        # Verify discount applied
        self.assertEqual(self.cart.discount_code, self.code)
        self.assertEqual(self.cart.final_total, Money(80, "USD"))

    def test_retroactive_discount_no_code(self):
        self.client.login(username='testuser', password='password')
        
        url = reverse('partner_retroactively_apply_discount', kwargs={
            'partner_slug': self.partner.slug,
            'cart_id': self.cart.id,
        })
        
        response = self.client.get(url)
        
        # Should redirect back to details page without changes
        self.assertEqual(response.status_code, 302)
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.discount_code)

    def test_retroactive_discount_already_refunded(self):
        self.cart.amount_refunded = Money(10, "USD")
        self.cart.save()
        
        self.client.login(username='testuser', password='password')
        
        url = reverse('partner_retroactively_apply_discount_with_code', kwargs={
            'partner_slug': self.partner.slug,
            'cart_id': self.cart.id,
            'discount_code': self.code.code
        })
        
        self.client.get(url)
        
        self.cart.refresh_from_db()
        # initial total 100, new total 80 -> refund 20. 10 + 20 = 30.
        self.assertEqual(self.cart.amount_refunded, Money(30, "USD"))
