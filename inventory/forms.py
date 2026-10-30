from decimal import Decimal

from django import forms

from .models import Customer, InventoryItem


class AddToBasketForm(forms.Form):
    sku = forms.CharField(label="Item ID", max_length=20)
    quantity = forms.IntegerField(min_value=1)
    price = forms.DecimalField(
        label="Price per unit",
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,  # blank means "use the listed price"
    )

    def clean(self):
        cleaned = super().clean()
        sku = cleaned.get("sku")
        quantity = cleaned.get("quantity")
        price = cleaned.get("price")

        # If a field already failed its own check, stop here
        if not sku or not quantity:
            return cleaned

        # 1. Find the item
        item = InventoryItem.objects.filter(sku__iexact=sku.strip()).first()
        if item is None:
            raise forms.ValidationError("No item found with that Item ID.")

        # 2. Zero-stock lockout
        if not item.is_active or item.stock_quantity == 0:
            raise forms.ValidationError(f"{item.name} is not available for sale.")

        # 3. Quantity check (the message never shows the stock number)
        if quantity > item.stock_quantity:
            raise forms.ValidationError(f"Not enough stock of {item.name} for that quantity.")

        # 4. Blank price means use the listed price
        if price is None:
            price = item.selling_price

        # 5. Price floor (the message never shows the minimum)
        if price < item.min_price:
            raise forms.ValidationError("That price is below the allowed minimum.")

        # Hand the checked values to the view
        cleaned["item"] = item
        cleaned["price"] = price
        return cleaned


class ConfirmSaleForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_active=True).order_by("name"),
        required=False,
        empty_label="Walk-in / cash customer",
        label="Customer",
    )
    customer_name = forms.CharField(
        max_length=100,
        required=False,
        label="Walk-in name (optional)",
    )
    amount_paid = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        label="Amount paid now (blank = pay in full)",
    )


class PaymentForm(forms.Form):
    """Money received from a customer who owes the shop."""
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_active=True).order_by("name"),
        empty_label="Choose a customer",
        label="Customer",
    )
    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Amount received",
    )
