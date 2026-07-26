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
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True) # (Price)
    quantity = models.IntegerField(default=0) # (Qty)
    date_ordered = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.item_number} in {self.report}"

    def set_product_from_item_number(self):
        from intake.distributors.hobbytyme import find_barcode_from_sku
        if "/" in self.item_number:
            parts = self.item_number.split("/")
            mfc_code = parts[0]
            sku = parts[1].split(" ")[0]
            barcode = find_barcode_from_sku(mfc_code, sku)
            if barcode:
                try:
                    self.product = Product.objects.get(barcode=barcode)
                except Product.DoesNotExist:
                    pass
