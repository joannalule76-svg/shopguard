from django.db import models
#This tells u all about the inventory item and its attributes
class InventoryItem(models.Model):
    sku = models.CharField("Item ID", max_length=20, unique=True)
    name = models.CharField(max_length=20)

    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    min_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):#This gives the string reperesentation of the inventory itemm which is displayedi in the admin panel
        return f"{self.sku} - {self.name}"

#this sales model links one model to another it can tell u which shopkeeper sold wat item and how may items were sold.
from django.conf import settings


# NEW: a registered customer who may take items on credit (created by the owner only)
class Customer(models.Model):  # NEW
    name = models.CharField(max_length=100)  # NEW
    phone = models.CharField(max_length=20, blank=True, default="")  # NEW
    credit_limit = models.DecimalField(  # NEW
        max_digits=12, decimal_places=2, default=0,  # NEW
        help_text="The most this customer may owe at one time. 0 means no credit.",  # NEW
    )  # NEW
    credit_days = models.PositiveIntegerField(  # NEW
        default=14,  # NEW
        help_text="Days the customer has to pay after taking items on credit.",  # NEW
    )  # NEW
    is_active = models.BooleanField(default=True)  # NEW
    created_at = models.DateTimeField(auto_now_add=True)  # NEW

    def __str__(self):  # NEW
        return self.name  # NEW


class Sale(models.Model):
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT, related_name="sales")  # NEW
    customer_name = models.CharField(max_length=100, blank=True, default="")  # NEW (name for walk-in customers)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_on_credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # NEW
    due_date = models.DateField(null=True, blank=True)  # NEW

    def __str__(self):
        return f"Sale #{self.pk} - {self.timestamp:%Y-%m-%d %H:%M}"

#Thismodel represents the individual items  sold in a sell.It links the sale to the inventory item and records the quantitiy sold
class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="sale_lines")
    quantity = models.PositiveIntegerField()
    unit_price_listed = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price_charged = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    closing_stock = models.PositiveIntegerField()
    def __str__(self):
        return f"{self.item.sku} x{self.quantity} (Sale #{self.sale_id})"
#This model represents the daily balance of the shop,including total cash,total items sold.
class DailyBalance(models.Model):
    date = modesls.DateField(unique=True)
    total_cash = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    credit_given = models.DecimalField(max_digits=16, decimal_places=2, default=0)  # NEW
    repayments_received = models.DecimalField(max_digits=16, decimal_places=2, default=0)  # NEW
    total_items_sold = models.PositiveIntegerField(default=0)
    transaction_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.date} - {self.total_cash}"

class SaleReversal(models.Model):
    sale_line = models.ForeignKey(SaleLine, on_delete=models.PROTECT, related_name="reversals")
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reversal of {self.sale_line} - {self.reason}"


# money received from a customer to pay down what they owe
class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="payments") 
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT) 
    timestamp = models.DateTimeField(auto_now_add=True) 

    def __str__(self):  
        return f"Payment #{self.pk} - {self.customer} - {self.amount}"  