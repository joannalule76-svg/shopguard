from django.contrib import admin

from .models import InventoryItem

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "selling_price", "stock_quantity", "is_active")
from .models import Sale, SaleLine

class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0
    readonly_fields = ("item", "quantity", "unit_price_listed",
                       "unit_price_charged", "unit_cost_price",
                       "line_total", "closing_stock")
    can_delete = False

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "timestamp", "cashier", "total_amount")
    list_filter = ("cashier", "timestamp")
    readonly_fields = ("cashier", "timestamp", "total_amount")
    inlines = [SaleLineInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import DailyBalance

@admin.register(DailyBalance)
class DailyBalanceAdmin(admin.ModelAdmin):
    list_display = ("date", "total_cash", "total_items_sold", "transaction_count")
    readonly_fields = ("date", "total_cash", "total_items_sold",
                       "transaction_count", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False



from .models import SaleReversal

@admin.register(SaleReversal)
class SaleReversalAdmin(admin.ModelAdmin):
    list_display = ("sale_line", "reversed_by", "reason", "timestamp")
    list_filter = ("reversed_by", "timestamp")
    readonly_fields = ("sale_line", "reversed_by", "reason", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


