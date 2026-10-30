from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Customer, DailyBalance, InventoryItem, Payment, Sale
from .services import SaleError, confirm_sale, credit_status, customer_balance, record_payment


class ShopTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("cashier", password="pw12345!")
        self.item = InventoryItem.objects.create(
            sku="SKU1", name="Soap", cost_price="500", selling_price="1000",
            min_price="800", stock_quantity=50,
        )
        self.customer = Customer.objects.create(name="Mama Joan", credit_limit="10000", credit_days=14)

    def basket(self, quantity=1, price="1000"):
        return [{"item_id": self.item.pk, "quantity": quantity, "price": price}]

    def today_book(self):
        return DailyBalance.objects.get(date=timezone.localdate())


class CreditSaleTests(ShopTestCase):
    def test_part_paid_sale_goes_on_credit(self):
        sale = confirm_sale(self.user, self.basket(5), customer=self.customer, amount_paid=Decimal("2000"))
        self.assertEqual(sale.total_amount, Decimal("5000"))
        self.assertEqual(sale.amount_on_credit, Decimal("3000"))
        self.assertEqual(sale.due_date, timezone.localdate() + timedelta(days=14))
        self.assertEqual(customer_balance(self.customer), Decimal("3000"))
        book = self.today_book()
        self.assertEqual(book.total_cash, Decimal("2000"))
        self.assertEqual(book.credit_given, Decimal("3000"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 45)

    def test_credit_needs_a_registered_customer(self):
        with self.assertRaises(SaleError):
            confirm_sale(self.user, self.basket(2), amount_paid=Decimal("0"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock_quantity, 50)  # nothing was saved

    def test_credit_limit_is_enforced(self):
        with self.assertRaises(SaleError):
            confirm_sale(self.user, self.basket(11), customer=self.customer, amount_paid=Decimal("0"))
        self.assertEqual(Sale.objects.count(), 0)

    def test_customer_without_credit_is_refused(self):
        no_credit = Customer.objects.create(name="Cash only", credit_limit=0)
        with self.assertRaises(SaleError):
            confirm_sale(self.user, self.basket(1), customer=no_credit, amount_paid=Decimal("0"))

    def test_paid_in_full_needs_no_credit_rules(self):
        sale = confirm_sale(self.user, self.basket(1), customer_name="Walk-in Sam")
        self.assertEqual(sale.amount_on_credit, Decimal("0"))
        self.assertIsNone(sale.due_date)
        self.assertEqual(sale.customer_name, "Walk-in Sam")


class PaymentTests(ShopTestCase):
    def owe(self, amount_units=5, paid="0"):
        return confirm_sale(self.user, self.basket(amount_units), customer=self.customer, amount_paid=Decimal(paid))

    def test_payment_reduces_balance_and_updates_cash_book(self):
        self.owe(5)  # owes 5000
        record_payment(self.user, self.customer, Decimal("1500"))
        self.assertEqual(customer_balance(self.customer), Decimal("3500"))
        self.assertEqual(self.today_book().repayments_received, Decimal("1500"))
        self.assertEqual(self.today_book().total_cash, Decimal("0"))  # repayments are kept on their own line

    def test_cannot_overpay(self):
        self.owe(2)
        with self.assertRaises(SaleError):
            record_payment(self.user, self.customer, Decimal("2001"))
        self.assertEqual(Payment.objects.count(), 0)

    def test_cannot_pay_when_nothing_is_owed(self):
        with self.assertRaises(SaleError):
            record_payment(self.user, self.customer, Decimal("100"))

    def test_zero_or_negative_payment_is_refused(self):
        self.owe(2)
        for amount in (Decimal("0"), Decimal("-5")):
            with self.assertRaises(SaleError):
                record_payment(self.user, self.customer, amount)

    def test_payment_makes_room_for_more_credit(self):
        self.owe(10)  # at the 10000 limit
        with self.assertRaises(SaleError):
            self.owe(1)
        record_payment(self.user, self.customer, Decimal("1000"))
        self.owe(1)
        self.assertEqual(customer_balance(self.customer), Decimal("10000"))


class OverdueTests(ShopTestCase):
    def test_payments_clear_the_oldest_credit_first(self):
        old = confirm_sale(self.user, self.basket(3), customer=self.customer, amount_paid=Decimal("0"))  # 3000
        new = confirm_sale(self.user, self.basket(2), customer=self.customer, amount_paid=Decimal("0"))  # 2000
        Sale.objects.filter(pk=old.pk).update(due_date=timezone.localdate() - timedelta(days=1))
        # Nothing paid yet: the old 3000 is overdue, the new 2000 is not
        self.assertEqual(credit_status(self.customer), (Decimal("5000"), Decimal("3000")))
        record_payment(self.user, self.customer, Decimal("1000"))
        self.assertEqual(credit_status(self.customer), (Decimal("4000"), Decimal("2000")))
        record_payment(self.user, self.customer, Decimal("2000"))
        self.assertEqual(credit_status(self.customer), (Decimal("2000"), Decimal("0")))


class ScreenTests(ShopTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="cashier", password="pw12345!")

    def put_in_basket(self, quantity=5):
        session = self.client.session
        session["basket"] = self.basket(quantity)
        session.save()

    def test_checkout_with_credit_through_the_screen(self):
        self.put_in_basket(5)
        self.client.post(reverse("sales_entry"), {
            "action": "confirm", "customer": self.customer.pk, "amount_paid": "2000",
        })
        sale = Sale.objects.get()
        self.assertEqual(sale.customer, self.customer)
        self.assertEqual(sale.amount_on_credit, Decimal("3000"))
        self.assertEqual(self.client.session["basket"], [])

    def test_bad_amount_keeps_the_basket(self):
        self.put_in_basket(5)
        self.client.post(reverse("sales_entry"), {"action": "confirm", "amount_paid": "NaN"})
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(len(self.client.session["basket"]), 1)

    def test_receive_payment_screen(self):
        confirm_sale(self.user, self.basket(5), customer=self.customer, amount_paid=Decimal("0"))
        response = self.client.post(reverse("receive_payment"), {"customer": self.customer.pk, "amount": "1000"})
        self.assertRedirects(response, reverse("customer_balances"))
        self.assertEqual(customer_balance(self.customer), Decimal("4000"))

    def test_balances_page_lists_who_owes(self):
        confirm_sale(self.user, self.basket(5), customer=self.customer, amount_paid=Decimal("0"))
        response = self.client.get(reverse("customer_balances"))
        self.assertContains(response, "Mama Joan")
        self.assertEqual(response.context["total_owed"], Decimal("5000"))

    def test_screens_need_login(self):
        self.client.logout()
        for name in ("sales_entry", "receive_payment", "customer_balances"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
