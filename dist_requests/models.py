from django.db import models

from intake.models import Distributor, PurchaseOrder
from partner.models import Partner
from shop.models import Product


class DistRequest(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE)
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, blank=True, null=True)
    request_name = models.CharField(max_length=300)
    date = models.DateField(blank=False)
    resolved = models.BooleanField(default=False,
                                   help_text="Has this request been addressed by the distributor" \
                                             " by fulfilling or allocating to 0")

    class Meta:
        unique_together = (
            ("partner", "distributor", "request_name"),
        )


class DistRequestLine(models.Model):
    request = models.ForeignKey(DistRequest, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = (
            ("request", "product"),
        )
