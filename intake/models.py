from datetime import datetime
from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum, F, Q, Value
from djmoney.models.fields import MoneyField
from djmoney.money import Money

from partner.models import Partner
from shop.models import Category, Product

PERCENTAGE_VALIDATOR = [MinValueValidator(0), MaxValueValidator(100)]


class Distributor(models.Model):
    dist_name = models.CharField(max_length=200)
    expected_filename = models.CharField(max_length=200, blank=True, null=True)
    individual_warehouse_files = models.BooleanField(default=False)

    dist_has_pricing_col = models.BooleanField(default=False,
                                               help_text="Determines if that column shows on purchase orders")

    def __str__(self):
        return self.dist_name

    class Meta:
        ordering = ["dist_name"]


class DistributorDiscount(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    discount_percentage = models.IntegerField(validators=PERCENTAGE_VALIDATOR)

    default = models.BooleanField(default=False)
    apply_to_publisher = models.ForeignKey('shop.Publisher', on_delete=models.CASCADE, blank=True, null=True,
                                           help_text="Only apply if the distributor has various publishers")
    apply_if_po_starts_with = models.CharField(max_length=10, blank=True, null=True)
    apply_if_pricing_col = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['distributor', 'default'],
                condition=Q(default=True),
                name='Only one default per distributor'
            )
        ]
        unique_together = (
            ("distributor", "apply_to_publisher"),
            ("distributor", "apply_if_po_starts_with"),
            ("distributor", "apply_if_pricing_col"),
        )

    def __str__(self):
        description = f"{self.distributor} {self.discount_percentage}%"
        if self.default:
            return description
        if self.apply_if_po_starts_with:
            return f"{description} if po starts with '{self.apply_if_po_starts_with}'"
        if self.apply_to_publisher:
            return f"{description} if publisher is '{self.apply_to_publisher}'"
        if self.apply_if_pricing_col:
            return f"{description} if pricing column is '{self.apply_if_pricing_col}'"


class Manufacturer(models.Model):
    """
    Deprecated, would like to switch all usages to shop publisher
    """

    mfc_name = models.CharField(max_length=200)

    def __str__(self):
        return self.mfc_name


class ManufacturerAbbreviation(models.Model):
    mfc = models.ForeignKey(Manufacturer, on_delete=models.CASCADE)
    distributor = models.ForeignKey(Distributor, on_delete=models.SET_NULL, blank=True, null=True)
    abbreviation = models.CharField(max_length=10)

    def __str__(self):
        return self.mfc.mfc_name + " - " + self.abbreviation


class ManufacturerBarcode(models.Model):
    mfc = models.ForeignKey(Manufacturer, on_delete=models.CASCADE)
    barcode_prefix = models.CharField(max_length=7)

    def __str__(self):
        return self.mfc.mfc_name + " - " + self.barcode_prefix

    class Meta:
        index_together = ["mfc", "barcode_prefix"]


class CategoryMap(models.Model):
    dist = models.ForeignKey(Distributor, on_delete=models.CASCADE, blank=True, null=True)
    mfc = models.ForeignKey(Manufacturer, on_delete=models.CASCADE, blank=True, null=True)
    mfc_cat_name = models.CharField(max_length=200, blank=True, null=True)
    category = models.ManyToManyField(Category, blank=True)

    def __str__(self):
        if self.mfc:
            return self.mfc.mfc_name + " -> " + self.category.name
        if self.dist:
            return self.dist.dist_name + " -> " + self.category.name


class TradeRange(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30)


class DistItem(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    dist_number = models.CharField(max_length=200, blank=True, null=True)
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.SET_NULL, blank=True, null=True)
    dist_name = models.CharField(max_length=200, blank=True, null=True)
    msrp = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', null=True)
    map = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', null=True)
    dist_price = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', null=True)
    dist_barcode = models.CharField(max_length=20, blank=True, null=True)
    dist_description = models.TextField(null=True)
    quantity_per_pack = models.IntegerField(blank=True, null=True)
    weight_lbs = models.DecimalField(decimal_places=3, max_digits=4, null=True)
    manually_entered = models.BooleanField(default=False)
    trade_range = models.ManyToManyField(TradeRange, related_name="contains")

    def __str__(self):
        return "{} {} {}".format(self.distributor, self.dist_number, self.dist_name)


class PurchaseOrder(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE)
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    date = models.DateField(null=True, help_text="Date Invoiced")
    date_received = models.DateField(null=True, blank=True, default=datetime.today)
    po_number = models.CharField(max_length=40, primary_key=True)
    archived = models.BooleanField(default=False)
    amount_charged = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', null=True)
    subtotal = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', null=True, blank=True)

    def __str__(self):
        return f"{self.distributor} {self.po_number}"

    def fee_ratio(self) -> Decimal:
        if not self.amount_charged:
            return Decimal(1.0)
        if self.subtotal:
            return self.amount_charged.amount / self.subtotal.amount
        else:
            return self.amount_charged.amount / self.get_line_total().amount

    def get_line_total(self):
        return sum(
            ((line.cost_per_item if line.cost_per_item is not None else Money(0, "USD")) * line.expected_quantity)
            for line in self.lines.all()
        )

    def get_total_item_count(self):
        return sum(line.quantity for line in self.lines.all())

    @property
    def calculated_total_cost(self):
        return self.lines.aggregate(sum=Sum(F('cost_per_item') * F('received_quantity')))['sum']

    @property
    def empty(self):
        return not self.lines.exists()

    @property
    def missing_costs(self):
        return self.lines.filter(cost_per_item__isnull=True).exists()

    @property
    def missing_quantities(self):
        return self.lines.filter(expected_quantity=None).exists() or self.lines.filter(received_quantity=None).exists()

    @property
    def cost_does_not_match_up(self):
        if self.subtotal:
            calculated = self.calculated_total_cost
            if calculated:
                return abs(calculated - self.subtotal.amount) > 1
        return True

    @property
    def completed(self):
        return not (self.empty or self.missing_costs
                    or self.missing_quantities or self.cost_does_not_match_up)

    def get_distributor_discount(self, line):
        distributor_discounts = DistributorDiscount.objects.filter(distributor=self.distributor)
        if distributor_discounts.count() == 1:
            return distributor_discounts.first()

        starts_with_discounts = distributor_discounts.alias(
            po_name=Value(self.po_number)
        ).filter(
            po_name__startswith=F('apply_if_po_starts_with')
        )
        if starts_with_discounts.count() == 1:
            return starts_with_discounts.first()

        if line.pricing and distributor_discounts.filter(apply_if_pricing_col=line.pricing).exists():
            return distributor_discounts.get(apply_if_pricing_col=line.pricing)

        if line.product.publisher and distributor_discounts.filter(apply_to_publisher=line.product.publisher).exists():
            return distributor_discounts.get(apply_to_publisher=line.product.publisher)

        if distributor_discounts.filter(default=True).exists():
            return distributor_discounts.get(default=True)
        return None


class POLine(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='lines')
    name = models.TextField(null=True, blank=True)
    barcode = models.CharField(max_length=20, blank=True, null=True)
    cost_per_item = MoneyField(max_digits=8, decimal_places=4, default_currency='USD', blank=True, null=True)
    msrp_on_line = MoneyField(max_digits=8, decimal_places=2, default_currency='USD', blank=True, null=True)
    expected_quantity = models.IntegerField(default=0)
    received_quantity = models.IntegerField(default=0)
    remaining_quantity = models.IntegerField(default=0)
    pricing = models.CharField(max_length=20, null=True, blank=True)  # For distributors like ACD (SDI, etc)
    line_number = models.IntegerField(default=0, null=True, blank=True)  # Used for ordering on view.

    def __str__(self):
        return f"{self.po.distributor} {self.po.po_number} {self.line_number}: {self.name} {self.barcode}"

    def line_subtotal(self):
        return self.cost_per_item * self.expected_quantity

    @property
    def actual_cost(self):
        if self.cost_per_item:
            return self.cost_per_item * self.po.fee_ratio()
        else:
            return None

    @property
    def product(self):
        if self.barcode:
            try:
                return Product.objects.get(barcode=self.barcode)
            except Exception:
                pass

    @property
    def dist_item(self):
        if self.barcode:
            try:
                return DistItem.objects.get(barcode=self.barcode, distributor=self.po.distributor)
            except Exception:
                pass
        if self.name:
            try:
                return DistItem.objects.get(dist_name=self.name, distributor=self.po.distributor)
            except Exception:
                pass

    def save(self, *args, **kwargs):
        """
        Try and grab properties from the dist item or product based on the name and barcode.
        :param args:
        :param kwargs:
        :return:
        """
        product = self.product

        if not self.name or not self.barcode or not self.cost_per_item:
            item = self.dist_item
            if item:
                if not self.barcode:
                    self.barcode = item.dist_barcode
                if not self.name:
                    self.name = item.dist_name
                if not self.cost_per_item:
                    self.cost_per_item = item.dist_price

        if product:
            self.name = product.name
        if self.line_number is None:
            self.line_number = self.po.lines.count
        return super(POLine, self).save(*args, **kwargs)


class DistributorWarehouse(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    warehouse_name = models.CharField(max_length=200)
    warehouse_filename = models.CharField(max_length=200)

    def __str__(self):
        return self.distributor.dist_name + " " + self.warehouse_name


class ItemWarehouseAvailability(models.Model):
    dist_item = models.ForeignKey(DistItem, on_delete=models.CharField)
    based_on_file = models.ManyToManyField('DistributorInventoryFile')
    warehouse = models.ForeignKey(DistributorWarehouse, on_delete=models.CASCADE, blank=True, null=True)
    in_stock = models.BooleanField(default=True)


class DistributorInventoryFile(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(DistributorWarehouse, on_delete=models.CASCADE, blank=True, null=True)
    file = models.FileField(upload_to='media/', max_length=500)
    processing = models.BooleanField(default=False)
    update_date = models.DateTimeField(blank=True)
    processed = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.update_date:
            self.update_date = datetime.utcnow()
        return super(DistributorInventoryFile, self).save(*args, **kwargs)

    def __str__(self):
        if self.warehouse:
            return self.distributor.dist_name + " " + self.warehouse.warehouse_name + " " + str(self.update_date)
        else:
            return self.distributor.dist_name + " " + str(self.update_date)

    def set_availability(self, item, warehouse, y_or_n, key="y"):
        availability, created = ItemWarehouseAvailability.objects.get_or_create(dist_item=item,
                                                                                warehouse=warehouse)
        if y_or_n == key:  # Item available in east warehouse
            availability.in_stock = True
        else:
            availability.in_stock = False
        availability.save()


class PricingRule(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE)
    priority = models.IntegerField(default=0)
    publisher = models.ForeignKey('shop.Publisher', blank=True, null=True, on_delete=models.CASCADE)
    percent_of_msrp = models.IntegerField(default=100)
    use_MAP = models.BooleanField(default=False, help_text="Uses the MAP, if available, instead of the MSRP")

    def __str__(self):
        product_string = "Products"
        if self.publisher:
            product_string = "{} products".format(self.publisher)

        return "{}: {} are {}% of msrp".format(self.priority, product_string, self.percent_of_msrp)
