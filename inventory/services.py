from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import DailyBalance, InventoryItem, Sale, SaleLine


class SaleError(Exception):
    """A sale could not be completed. The message is safe to show the shopkeeper."""


@transaction.atomic
def confirm_sale(user, basket):
    if not basket:
        raise SaleError("The sale is empty. Add at least one item first.")

    prepared_lines = []
    total_cash = Decimal("0.00")
    total_units = 0

    for entry in basket:
        quantity = entry["quantity"]
        price = Decimal(entry["price"])

        # Re-check everything now: this is the check that counts
        item = InventoryItem.objects.filter(pk=entry["item_id"]).first()
        if item is None:
            raise SaleError("An item in this sale no longer exists. Nothing was saved.")
        if not item.is_active:
            raise SaleError(f"{item.name} is not available for sale. Nothing was saved.")
        if price < item.min_price:
            raise SaleError(f"The price for {item.name} is below the allowed minimum. Nothing was saved.")

        # Take the stock off, only if enough is left
        taken = InventoryItem.objects.filter(
            pk=item.pk, stock_quantity__gte=quantity
        ).update(stock_quantity=F("stock_quantity") - quantity)
        if taken == 0:
            raise SaleError(f"Not enough stock of {item.name}. Nothing was saved.")

        item.refresh_from_db()  # now holds the stock left after this line
        line_total = price * quantity
        prepared_lines.append({
            "item": item,
            "quantity": quantity,
            "listed": item.selling_price,
            "charged": price,
            "cost": item.cost_price,
            "line_total": line_total,
            "closing_stock": item.stock_quantity,
        })
        total_cash += line_total
        total_units += quantity

    # Every item passed: now write the permanent records
    sale = Sale.objects.create(cashier=user, total_amount=total_cash)
    for line in prepared_lines:
        SaleLine.objects.create(
            sale=sale,
            item=line["item"],
            quantity=line["quantity"],
            unit_price_listed=line["listed"],
            unit_price_charged=line["charged"],
            unit_cost_price=line["cost"],
            line_total=line["line_total"],
            closing_stock=line["closing_stock"],
        )

    # Add this sale to today's cash book
    balance, _ = DailyBalance.objects.get_or_create(date=timezone.localdate())
    DailyBalance.objects.filter(pk=balance.pk).update(
        total_cash=F("total_cash") + total_cash,
        total_items_sold=F("total_items_sold") + total_units,
        transaction_count=F("transaction_count") + 1,
        updated_at=timezone.now(),
    )

    return sale