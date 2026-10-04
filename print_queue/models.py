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


class Printer(models.Model):
    partner = models.ForeignKey('partner.Partner', on_delete=models.CASCADE)
    client_id = models.CharField(max_length=255, unique=True, help_text="UUID from localStorage")
    name = models.CharField(max_length=255, help_text="User-defined name for the printer")
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.client_id})"


class PrintJob(models.Model):
    JOB_TYPE_CHOICES = [('RECEIPT', 'Receipt'), ('LABEL', 'Label'), ('RAW', 'Raw')]
    STATUS_CHOICES = [('PENDING', 'Pending'), ('CLAIMED', 'Claimed'), ('PRINTED', 'Printed'), ('FAILED', 'Failed')]

    partner = models.ForeignKey('partner.Partner', on_delete=models.CASCADE)
    destination_printer = models.ForeignKey(Printer, on_delete=models.SET_NULL, null=True, blank=True)
    job_type = models.CharField(max_length=10, choices=JOB_TYPE_CHOICES)
    payload = models.JSONField(help_text="Data required for printing")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job_type} job for {self.partner} - {self.status}"
