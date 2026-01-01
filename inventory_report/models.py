from django.db import models

from shop.models import Product


class InventoryReport(models.Model):
    date = models.DateField()
    partner = models.ForeignKey("partner.Partner", on_delete=models.CASCADE)

    def __str__(self):
        return "{} inventory report from {}".format(self.partner, self.date)


class InventoryReportLocation(models.Model):
    name = models.CharField(max_length=200)
    partner = models.ForeignKey("partner.Partner", on_delete=models.CharField)

    def __str__(self):
        return self.name


class InventoryReportLine(models.Model):
    report = models.ForeignKey(InventoryReport, on_delete=models.CASCADE, related_name='report_lines')
    location = models.ForeignKey(InventoryReportLocation, on_delete=models.SET_NULL, null=True)
    barcode = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now=True)
    name_at_time_of_scan = models.CharField(max_length=200, blank=True, null=True)
    product_at_time_of_scan = models.ForeignKey(Product, on_delete=models.SET_NULL, blank=True, null=True)
    number_at_time_of_scan = models.IntegerField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.name_at_time_of_scan:
            potential_product = Product.objects.filter(barcode=self.barcode)
            if potential_product.exists():
                product = potential_product.first()
                self.product_at_time_of_scan = product
                self.name_at_time_of_scan = product.name
            else:
                self.name_at_time_of_scan = "No Product"
        if not self.number_at_time_of_scan:
            self.number_at_time_of_scan = self.report.report_lines.filter(
                barcode=self.barcode).count() + 1  # Because it doesn't count itself yet
        return super(InventoryReportLine, self).save(*args, **kwargs)

    def __str__(self):
        base_name = f""
        if self.name_at_time_of_scan:
            base_name = f"{self.name_at_time_of_scan} {self.barcode}"
        if self.location:
            base_name = f"{base_name} in {self.location}"
        return f"{base_name}, scanned at {self.timestamp}"
