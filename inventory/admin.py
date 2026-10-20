from django.contrib import admin

from .models import (
    Customer, DailyBalance, InventoryItem, Payment, Sale, SaleLine, SaleReversal,
)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "selling_price", "stock_quantity", "is_active")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "credit_limit", "credit_days", "is_active")
    search_fields = ("name", "phone")
    list_filter = ("is_active",)


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0
    readonly_fields = ("item", "quantity", "unit_price_listed",
                       "unit_price_charged", "unit_cost_price",
                       "line_total", "closing_stock")
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "timestamp", "cashier", "customer", "customer_name",
                    "total_amount", "amount_on_credit", "due_date")
    list_filter = ("cashier", "timestamp")
    search_fields = ("customer_name", "customer__name")
    readonly_fields = ("cashier", "timestamp", "customer", "customer_name",
                       "total_amount", "amount_on_credit", "due_date")
    inlines = [SaleLineInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DailyBalance)
class DailyBalanceAdmin(admin.ModelAdmin):
    list_display = ("date", "total_cash", "credit_given", "repayments_received",
                    "total_items_sold", "transaction_count")
    readonly_fields = ("date", "total_cash", "credit_given", "repayments_received",
                       "total_items_sold", "transaction_count", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SaleReversal)
class SaleReversalAdmin(admin.ModelAdmin):
    list_display = ("sale_line", "reversed_by", "reason", "timestamp")
    list_filter = ("reversed_by", "timestamp")
    readonly_fields = ("sale_line", "reversed_by", "reason", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "amount", "received_by", "timestamp")
    list_filter = ("received_by", "timestamp")
    search_fields = ("customer__name",)
    readonly_fields = ("customer", "amount", "received_by", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False