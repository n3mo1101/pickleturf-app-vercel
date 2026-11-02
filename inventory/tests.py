# inventory/tests.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from inventory.models import Category, InventoryItem, RentalRecord, Sale
from inventory.services import (
    process_sale,
    process_rental,
    return_rental,
    adjust_stock,
)

User = get_user_model()


class InventoryStockTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            email='staff@test.com',
            password='testpass123',
            first_name='Staff',
            last_name='User',
        )
        self.category = Category.objects.create(name='Paddles')
        self.sale_item = InventoryItem.objects.create(
            name='Pro Paddle',
            category=self.category,
            item_type=InventoryItem.ItemType.SALE,
            sale_price=2500,
            stock=10,
        )
        self.rent_item = InventoryItem.objects.create(
            name='Court Shoes',
            category=self.category,
            item_type=InventoryItem.ItemType.RENT,
            rent_price=100,
            stock=5,
        )
        self.both_item = InventoryItem.objects.create(
            name='Starter Paddle',
            category=self.category,
            item_type=InventoryItem.ItemType.BOTH,
            sale_price=1200,
            rent_price=80,
            stock=8,
        )

    # ── Stock Adjustment ──────────────────────────────────────

    def test_add_stock(self):
        adjust_stock(self.sale_item, 5, 'add')
        self.sale_item.refresh_from_db()
        self.assertEqual(self.sale_item.stock, 15)

    def test_deduct_stock(self):
        adjust_stock(self.sale_item, 3, 'deduct')
        self.sale_item.refresh_from_db()
        self.assertEqual(self.sale_item.stock, 7)

    def test_deduct_more_than_stock_raises_error(self):
        with self.assertRaises(ValidationError):
            adjust_stock(self.sale_item, 99, 'deduct')

    def test_invalid_action_raises_error(self):
        with self.assertRaises(ValueError):
            adjust_stock(self.sale_item, 1, 'invalid')

    # ── POS Sale ──────────────────────────────────────────────

    def test_sale_deducts_stock(self):
        process_sale(
            cart_items=[{'item': self.sale_item, 'quantity': 3}],
            created_by=self.staff,
        )
        self.sale_item.refresh_from_db()
        self.assertEqual(self.sale_item.stock, 7)

    def test_sale_creates_sale_record(self):
        process_sale(
            cart_items=[{'item': self.sale_item, 'quantity': 2}],
            created_by=self.staff,
        )
        self.assertEqual(Sale.objects.count(), 1)

    def test_sale_computes_correct_total(self):
        sale = process_sale(
            cart_items=[
                {'item': self.sale_item, 'quantity': 2},  # 2500 × 2 = 5000
                {'item': self.both_item, 'quantity': 1},  # 1200 × 1 = 1200
            ],
            created_by=self.staff,
        )
        self.assertEqual(sale.total, 6200)

    def test_sale_creates_paid_transaction(self):
        from transactions.models import Transaction
        sale = process_sale(
            cart_items=[{'item': self.sale_item, 'quantity': 1}],
            created_by=self.staff,
        )
        tx = Transaction.objects.get(sale=sale)
        self.assertEqual(tx.payment_status, Transaction.PaymentStatus.PAID)

    def test_sale_with_insufficient_stock_raises_error(self):
        with self.assertRaises(ValidationError):
            process_sale(
                cart_items=[{'item': self.sale_item, 'quantity': 999}],
                created_by=self.staff,
            )

    def test_sale_of_rent_only_item_raises_error(self):
        with self.assertRaises(ValidationError):
            process_sale(
                cart_items=[{'item': self.rent_item, 'quantity': 1}],
                created_by=self.staff,
            )

    def test_empty_cart_raises_error(self):
        with self.assertRaises(ValidationError):
            process_sale(cart_items=[], created_by=self.staff)

    def test_all_or_nothing_on_stock_error(self):
        """If one item fails validation, no stock should be deducted."""
        original_stock = self.sale_item.stock
        with self.assertRaises(ValidationError):
            process_sale(
                cart_items=[
                    {'item': self.sale_item, 'quantity': 1},
                    {'item': self.rent_item, 'quantity': 1},  # invalid
                ],
                created_by=self.staff,
            )
        self.sale_item.refresh_from_db()
        self.assertEqual(self.sale_item.stock, original_stock)

    # ── Rental ────────────────────────────────────────────────

    def test_rental_deducts_stock(self):
        process_rental(
            cart_items=[{'item': self.rent_item, 'quantity': 2}],
            renter_name='John Doe',
        )
        self.rent_item.refresh_from_db()
        self.assertEqual(self.rent_item.stock, 3)

    def test_rental_creates_record(self):
        process_rental(
            cart_items=[{'item': self.rent_item, 'quantity': 1}],
            renter_name='Jane Smith',
            renter_contact='09171234567',
        )
        self.assertEqual(RentalRecord.objects.count(), 1)
        record = RentalRecord.objects.first()
        self.assertEqual(record.renter_name, 'Jane Smith')
        self.assertEqual(record.renter_contact, '09171234567')

    def test_rental_computes_correct_total(self):
        records, total = process_rental(
            cart_items=[
                {'item': self.rent_item, 'quantity': 2},  # 100 × 2 = 200
                {'item': self.both_item, 'quantity': 1},  # 80  × 1 = 80
            ],
            renter_name='Walk In',
        )
        self.assertEqual(total, 280)

    def test_rental_creates_paid_transaction(self):
        from transactions.models import Transaction
        process_rental(
            cart_items=[{'item': self.rent_item, 'quantity': 1}],
            renter_name='Walk In',
        )
        self.assertTrue(
            Transaction.objects.filter(
                tx_type='rental',
                payment_status='paid',
            ).exists()
        )

    def test_rental_of_sale_only_item_raises_error(self):
        with self.assertRaises(ValidationError):
            process_rental(
                cart_items=[{'item': self.sale_item, 'quantity': 1}],
                renter_name='Test',
            )

    def test_rental_without_renter_name_raises_error(self):
        with self.assertRaises(ValidationError):
            process_rental(
                cart_items=[{'item': self.rent_item, 'quantity': 1}],
                renter_name='',
            )

    def test_rental_insufficient_stock_raises_error(self):
        with self.assertRaises(ValidationError):
            process_rental(
                cart_items=[{'item': self.rent_item, 'quantity': 999}],
                renter_name='Test',
            )

    # ── Return ────────────────────────────────────────────────

    def test_return_restores_stock(self):
        records, _ = process_rental(
            cart_items=[{'item': self.rent_item, 'quantity': 2}],
            renter_name='Walk In',
        )
        return_rental(records[0])
        self.rent_item.refresh_from_db()
        self.assertEqual(self.rent_item.stock, 5)   # fully restored

    def test_return_updates_status(self):
        records, _ = process_rental(
            cart_items=[{'item': self.rent_item, 'quantity': 1}],
            renter_name='Walk In',
        )
        return_rental(records[0])
        records[0].refresh_from_db()
        self.assertEqual(records[0].status, RentalRecord.Status.RETURNED)

    def test_double_return_raises_error(self):
        records, _ = process_rental(
            cart_items=[{'item': self.rent_item, 'quantity': 1}],
            renter_name='Walk In',
        )
        return_rental(records[0])
        with self.assertRaises(ValidationError):
            return_rental(records[0])


class InventoryModalViewTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            email='inventory@test.com',
            password='testpass123',
            first_name='Inventory',
            last_name='Staff',
            role='staff',
            is_staff=True,
        )
        self.category = Category.objects.create(name='Accessories')
        self.item = InventoryItem.objects.create(
            name='Grip Tape',
            category=self.category,
            item_type=InventoryItem.ItemType.SALE,
            sale_price=150,
            stock=10,
        )
        self.client.force_login(self.staff)

    def test_stock_modal_returns_partial(self):
        response = self.client.get(
            reverse('inventory:admin_stock', args=[self.item.pk]),
            {'modal': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'inventory/_stock_adjust_modal.html'
        )
        self.assertNotContains(response, '<!DOCTYPE html>')
        self.assertContains(response, 'Current stock')

    def test_stock_adjust_redirects_to_next(self):
        response = self.client.post(
            reverse('inventory:admin_stock', args=[self.item.pk]),
            {
                'action': 'add',
                'quantity': 5,
                'next': reverse('inventory:admin_list'),
            },
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 15)
        self.assertEqual(response.url, reverse('inventory:admin_list'))

    def test_stock_adjust_error_stays_in_modal(self):
        response = self.client.post(
            reverse('inventory:admin_stock', args=[self.item.pk]),
            {
                'action': 'deduct',
                'quantity': 99,
                'next': reverse('inventory:admin_list'),
            },
            HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'inventory/_stock_adjust_modal.html'
        )
        self.assertContains(response, 'Insufficient stock')
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 10)

    def test_category_create_modal_returns_partial(self):
        response = self.client.get(
            reverse('inventory:admin_category_create'),
            {'modal': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'inventory/_category_modal.html'
        )
        self.assertNotContains(response, '<!DOCTYPE html>')

    def test_category_edit_modal_prefills_form(self):
        response = self.client.get(
            reverse('inventory:admin_category_edit', args=[self.category.pk]),
            {'modal': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'inventory/_category_modal.html'
        )
        self.assertContains(response, self.category.name)

    def test_category_create_from_modal(self):
        response = self.client.post(
            reverse('inventory:admin_category_create'),
            {'name': 'Balls', 'description': 'Game balls'},
            HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertEqual(response.url, reverse('inventory:admin_categories'))
        self.assertTrue(Category.objects.filter(name='Balls').exists())

    def test_category_invalid_modal_rerenders_with_errors(self):
        response = self.client.post(
            reverse('inventory:admin_category_create'),
            {'name': self.category.name, 'description': ''},
            HTTP_X_REQUESTED_WITH='fetch',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, 'inventory/_category_modal.html'
        )
        self.assertContains(response, 'already exists')