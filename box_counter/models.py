from django.db import models

from partner.models import Partner


# Create your models here.

class BoxPurchase(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE)
    date = models.DateField(null=True)
    order_number = models.CharField(max_length=40, primary_key=True)


class BoxInventory(models.Model):
    description = models.CharField(max_length=40)
    length_inches = models.PositiveIntegerField()
    width_inches = models.PositiveIntegerField()
    height_inches = models.PositiveIntegerField()
    barcode = models.CharField(max_length=40, unique=True)

    current_inventory = models.PositiveIntegerField()

    def __str__(self):
        return self.description


class BoxUse(models.Model):
    box = models.ForeignKey(BoxInventory, on_delete=models.PROTECT)
    cart = models.ForeignKey('checkout.Cart', on_delete=models.PROTECT, related_name='used_boxes')

    def __str__(self):
        return f"{self.box.description} on order {self.cart.id}"
