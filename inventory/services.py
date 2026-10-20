from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import Customer, DailyBalance, InventoryItem, Payment, Sale, SaleLine


class SaleError(Exception):
    """A sale could not be completed. The message is safe to show the shopkeeper."""


def customer_balance(customer):
    """What the customer owes: credit given on their sales, minus their payments."""
    credit = Sale.objects.filter(customer=customer).aggregate(t=Sum("amount_on_credit"))["t"] or Decimal("0.00")
    paid = Payment.objects.filter(customer=customer).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
    return credit - paid


@transaction.atomic
def confirm_sale(user, basket, customer=None, amount_paid=None, customer_name=""):
    if not basket:
        raise SaleError("The sale is empty. Add at least one item first.")

    # The total, worked out from the prices in the draft
    total = sum((Decimal(e["price"]) * e["quantity"] for e in basket), Decimal("0.00"))

    # How much is paid now, and how much is left on credit
    if amount_paid is None:
        amount_paid = total
    if amount_paid < 0 or amount_paid > total:
        raise SaleError("The amount paid must be between 0 and the sale total. Nothing was saved.")
    on_credit = total - amount_paid

    # Read the customer fresh from the database
    if customer is not None:
        customer = Customer.objects.filter(pk=customer.pk).first()
        if customer is None:
            raise SaleError("That customer no longer exists. Nothing was saved.")

    # Credit rules (checked before any stock is touched)
    due_date = None
    if on_credit > 0:
        if customer is None:
            raise SaleError("Credit can only be given to a registered customer. Nothing was saved.")
        if not customer.is_active or customer.credit_limit <= 0:
            raise SaleError(f"{customer.name} is not allowed credit. Nothing was saved.")
        if customer_balance(customer) + on_credit > customer.credit_limit:
            raise SaleError(f"This sale would take {customer.name} over their credit limit. Nothing was saved.")
        due_date = timezone.localdate() + timedelta(days=customer.credit_days)

    prepared_lines = []
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
        prepared_lines.append({
            "item": item,
            "quantity": quantity,
            "listed": item.selling_price,
            "charged": price,
            "cost": item.cost_price,
            "line_total": price * quantity,
            "closing_stock": item.stock_quantity,
        })
        total_units += quantity

    # Every check passed: now write the permanent records
    walk_in_name = "" if customer else (customer_name or "").strip()[:100]
    sale = Sale.objects.create(
        cashier=user,
        customer=customer,
        customer_name=walk_in_name,
        total_amount=total,
        amount_on_credit=on_credit,
        due_date=due_date,
    )
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

    # Add this sale to today's cash book: only the money paid now counts as cash
    balance, _ = DailyBalance.objects.get_or_create(date=timezone.localdate())
    DailyBalance.objects.filter(pk=balance.pk).update(
        total_cash=F("total_cash") + amount_paid,
        credit_given=F("credit_given") + on_credit,
        total_items_sold=F("total_items_sold") + total_units,
        transaction_count=F("transaction_count") + 1,
        updated_at=timezone.now(),
    )

    return sale