from django.db import models
from intake.models import Distributor, PurchaseOrder
from shop.models import Product
from partner.models import Partner

class BackorderReport(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE)
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    retrieved = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.partner} - {self.distributor} backorder report at {self.retrieved}"

class BackorderReportLine(models.Model):
    report = models.ForeignKey(BackorderReport, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, blank=True, null=True)
    
    # Data from the report
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    item_number = models.CharField(max_length=200) # e.g. VAL/72001 (Part Number)
    description = models.CharField(max_length=500, blank=True, null=True) # (Product)
    msrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True) # (Price)
    quantity = models.IntegerField(default=0) # (Qty)
    date_ordered = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_number} in {self.report}"

    def set_product_from_item_number(self):
        from intake.models import DistItem
        dist_item, _ = DistItem.objects.get_or_create(distributor=self.report.distributor,
                                                      dist_number=self.item_number)
        dist_item.set_product_from_sku()
        if dist_item.product:
            self.product = dist_item.product
