from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from crm.models import County, Customer
from datetime import date

from job.billing_schedule import (
    BILLING_SCHEDULE_MARKER,
    CHANGE_ORDER_COMMENT,
    build_billing_schedule_lines,
    contract_total_for_job,
    create_change_order_billing_sales,
    ensure_reverse_wip_amount,
    has_billing_schedule,
    sync_billing_schedule_sales,
)
from job.models import ChangeOrder, Job, Sale
from product.models import ProductCode

User = get_user_model()


class BillingScheduleTests(TestCase):
    def setUp(self):
        self.county = County.objects.create(name='Test County', taxrate=0.07)
        self.customer = Customer.objects.create(
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
            address='1 Main St',
            city='Madison',
            zip='53703',
            county=self.county,
        )
        self.job = Job.objects.create(
            customer=self.customer,
            county=self.county,
            sold=True,
            saleamount=Decimal('50000.00'),
        )
        self.slw = ProductCode.objects.create(code='SLW', description='Site Labor WIP')
        self.fl = ProductCode.objects.create(code='FL', description='Flooring')

    def test_under_10k_schedule(self):
        lines = build_billing_schedule_lines(Decimal('8000'))
        comments = [line['comment'] for line in lines]
        self.assertEqual(comments, ['Deposit', 'Completion', BILLING_SCHEDULE_MARKER])
        self.assertEqual(lines[0]['amount'], Decimal('6000.00'))
        self.assertEqual(lines[1]['amount'], Decimal('2000.00'))
        self.assertEqual(lines[2]['amount'], Decimal('-8000.00'))

    def test_10k_and_up_schedule(self):
        lines = build_billing_schedule_lines(Decimal('50000'))
        amounts = {line['comment']: line['amount'] for line in lines}
        self.assertEqual(amounts['Deposit'], Decimal('20000.00'))
        self.assertEqual(amounts['Start'], Decimal('10000.00'))
        self.assertEqual(amounts['Rough'], Decimal('10000.00'))
        self.assertEqual(amounts['Functional'], Decimal('7500.00'))
        self.assertEqual(amounts['Punch'], Decimal('2500.00'))
        self.assertEqual(amounts[BILLING_SCHEDULE_MARKER], Decimal('-50000.00'))

    def test_exact_10k_uses_upper_tier(self):
        lines = build_billing_schedule_lines(Decimal('10000'))
        comments = [line['comment'] for line in lines]
        self.assertEqual(
            comments,
            ['Deposit', 'Start', 'Rough', 'Functional', 'Punch', BILLING_SCHEDULE_MARKER],
        )
        self.assertEqual(lines[0]['amount'], Decimal('4000.00'))
        self.assertEqual(lines[4]['amount'], Decimal('500.00'))

    def test_sync_creates_slw_sales(self):
        user = User.objects.create_user(username='acct', password='x')
        Sale.objects.create(
            job=self.job,
            product_code=self.fl,
            sale_amount=Decimal('50000.00'),
            comment='Flooring',
        )
        result = sync_billing_schedule_sales(self.job, created_by=user)
        self.assertEqual(result['created'], 6)
        self.assertTrue(has_billing_schedule(self.job))
        slw_sales = Sale.objects.filter(job=self.job, product_code=self.slw)
        self.assertEqual(slw_sales.count(), 6)
        self.assertTrue(slw_sales.filter(comment=BILLING_SCHEDULE_MARKER).exists())
        reverse_wip = slw_sales.get(comment=BILLING_SCHEDULE_MARKER)
        self.assertEqual(reverse_wip.sale_amount, Decimal('-50000.00'))
        net_total = sum(s.sale_amount for s in self.job.sales.all())
        self.assertEqual(net_total, Decimal('50000.00'))

    def test_sync_is_idempotent(self):
        Sale.objects.create(
            job=self.job,
            product_code=self.fl,
            sale_amount=Decimal('50000.00'),
        )
        sync_billing_schedule_sales(self.job)
        result = sync_billing_schedule_sales(self.job)
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['reason'], 'already_exists')

    def test_contract_total_from_sales_excludes_slw(self):
        Sale.objects.create(job=self.job, product_code=self.fl, sale_amount=Decimal('12000.00'))
        Sale.objects.create(job=self.job, product_code=self.slw, sale_amount=Decimal('1.00'), comment='Deposit')
        self.assertEqual(contract_total_for_job(self.job), Decimal('12000.00'))

    def test_ensure_reverse_wip_corrects_positive_amount(self):
        Sale.objects.create(job=self.job, product_code=self.fl, sale_amount=Decimal('50000.00'))
        Sale.objects.create(
            job=self.job,
            product_code=self.slw,
            sale_amount=Decimal('50000.00'),
            comment=BILLING_SCHEDULE_MARKER,
        )
        self.assertTrue(ensure_reverse_wip_amount(self.job))
        rw = Sale.objects.get(job=self.job, comment=BILLING_SCHEDULE_MARKER)
        self.assertEqual(rw.sale_amount, Decimal('-50000.00'))

    def test_change_order_creates_billing_and_reverse_wip(self):
        Sale.objects.create(job=self.job, product_code=self.fl, sale_amount=Decimal('50000.00'))
        sync_billing_schedule_sales(self.job)
        original_rw = Sale.objects.get(
            job=self.job,
            comment=BILLING_SCHEDULE_MARKER,
            notes='',
        )
        self.assertEqual(original_rw.sale_amount, Decimal('-50000.00'))

        co = ChangeOrder.objects.create(
            job=self.job,
            description='Add island',
            amount=Decimal('2500.00'),
            order_date=date.today(),
            tax='UT',
        )
        result = create_change_order_billing_sales(co)
        self.assertEqual(result['created'], 2)

        co_sale = Sale.objects.get(job=self.job, comment=CHANGE_ORDER_COMMENT)
        self.assertEqual(co_sale.sale_amount, Decimal('2500.00'))
        self.assertEqual(co_sale.product_code, self.slw)

        co_rw = Sale.objects.get(
            job=self.job,
            comment=BILLING_SCHEDULE_MARKER,
            notes=f'change_order:{co.id}',
        )
        self.assertEqual(co_rw.sale_amount, Decimal('-2500.00'))

        original_rw.refresh_from_db()
        self.assertEqual(original_rw.sale_amount, Decimal('-50000.00'))

        # Idempotent
        again = create_change_order_billing_sales(co)
        self.assertEqual(again['created'], 0)
        self.assertEqual(again['reason'], 'already_exists')

        # ensure_reverse_wip must not rewrite CO reverse wip or original
        self.assertFalse(ensure_reverse_wip_amount(self.job))
        original_rw.refresh_from_db()
        co_rw.refresh_from_db()
        self.assertEqual(original_rw.sale_amount, Decimal('-50000.00'))
        self.assertEqual(co_rw.sale_amount, Decimal('-2500.00'))

    def test_change_order_without_amount_skips_billing(self):
        co = ChangeOrder.objects.create(
            job=self.job,
            description='Non-monetary note',
            amount=None,
            order_date=date.today(),
        )
        result = create_change_order_billing_sales(co)
        self.assertEqual(result['created'], 0)
        self.assertEqual(result['reason'], 'no_amount')
        self.assertFalse(Sale.objects.filter(job=self.job, comment=CHANGE_ORDER_COMMENT).exists())
