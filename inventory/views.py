from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import AddToBasketForm
from .models import InventoryItem
from .services import SaleError, confirm_sale


@login_required
def home(request):
    # Admin (owner) goes to the admin panel, Staff goes to the sales screen
    if request.user.is_superuser:
        return redirect("admin:index")
    return redirect("sales_entry")


def build_lines(basket):
    """Turns the saved draft list into lines the screen can show, plus the total."""
    lines = []
    total = Decimal("0.00")
    for index, entry in enumerate(basket):
        item = InventoryItem.objects.filter(pk=entry["item_id"]).first()
        if item is None:
            continue
        price = Decimal(entry["price"])
        line_total = price * entry["quantity"]
        total += line_total
        lines.append({
            "index": index,
            "item": item,
            "quantity": entry["quantity"],
            "price": price,
            "line_total": line_total,
        })
    return lines, total


@login_required
def sales_entry(request):
    basket = request.session.get("basket", [])
    form = AddToBasketForm()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            form = AddToBasketForm(request.POST)
            if form.is_valid():
                item = form.cleaned_data["item"]
                quantity = form.cleaned_data["quantity"]
                price = form.cleaned_data["price"]

                # Same item added twice: check the combined quantity too
                already = sum(e["quantity"] for e in basket if e["item_id"] == item.pk)
                if already + quantity > item.stock_quantity:
                    messages.error(request, f"Not enough stock of {item.name} for that quantity.")
                else:
                    basket.append({
                        "item_id": item.pk,
                        "quantity": quantity,
                        "price": str(price),
                    })
                    request.session["basket"] = basket
                return redirect("sales_entry")
            # If the form has errors, fall through and show the page with the messages

        elif action == "remove":
            try:
                basket.pop(int(request.POST.get("index", "")))
                request.session["basket"] = basket
            except (ValueError, IndexError):
                pass
            return redirect("sales_entry")

        elif action == "clear":
            request.session["basket"] = []
            return redirect("sales_entry")

        elif action == "confirm":
            try:
                sale = confirm_sale(request.user, basket)
            except SaleError as error:
                messages.error(request, str(error))  # the draft stays, nothing was saved
            else:
                request.session["basket"] = []
                messages.success(request, f"Sale #{sale.pk} recorded. Total: {sale.total_amount}")
            return redirect("sales_entry")

    lines, total = build_lines(basket)
    return render(request, "inventory/sales_entry.html", {
        "form": form,
        "lines": lines,
        "total": total,
    })