from decimal import Decimal

from django import forms

from .models import InventoryItem


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