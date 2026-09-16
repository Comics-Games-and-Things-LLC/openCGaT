from django.db import models
from djmoney.models.fields import MoneyField


class PrintQueueItem(models.Model):
    inventory_item = models.ForeignKey('shop.InventoryItem', on_delete=models.CASCADE)
    quantity_at_adjustment = models.IntegerField(help_text="Quantity in stock when the price change was detected")
    quantity_at_printing = models.IntegerField(null=True, blank=True, help_text="Quantity in stock when printing started")
    old_price = MoneyField(max_digits=19, decimal_places=2, default_currency='USD')
    new_price = MoneyField(max_digits=19, decimal_places=2, default_currency='USD')
    printed = models.BooleanField(default=False)
    printed_at = models.DateTimeField(null=True, blank=True)
    restickered = models.BooleanField(default=False)
    restickered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.inventory_item.product} - {self.old_price} to {self.new_price}"
