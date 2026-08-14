"""Shared data builder for Sales Orders list and PDF report."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import DateField, DecimalField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, TruncDate

from .billing_schedule import SLW_CODE
from .models import ChangeOrder, Job, Payment, Sale


def _parse_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def build_sales_orders_report(request) -> dict:
    """
    Build sales-order report data from the same filters as the Sales order page.
    Returns grouped rows, flat rows for PDF, totals, and filter metadata.
    """
    user_filter = (request.GET.get('user') or '').strip()
    if user_filter.lower() in {'all', 'none'}:
        user_filter = ''
    start_date = (request.GET.get('start_date') or '').strip()
    end_date = (request.GET.get('end_date') or '').strip()
    search_query = (request.GET.get('search') or '').strip()

    excluded_usernames = ['bill', 'billy', 'txin214', 'admin', 'myname']
    all_users = User.objects.exclude(
        username__in=excluded_usernames
    ).exclude(
        Q(first_name__iexact='mu') & Q(last_name__iexact='name')
    ).order_by('first_name', 'last_name', 'username')

    start_date_obj = _parse_date(start_date)
    end_date_obj = _parse_date(end_date)

    change_order_total_sq = (
        ChangeOrder.objects.filter(job_id=OuterRef('pk'))
        .values('job_id')
        .annotate(total=Sum('amount'))
        .values('total')[:1]
    )
    contract_sales_total_sq = (
        Sale.objects.filter(job_id=OuterRef('pk'))
        .exclude(product_code__code=SLW_CODE)
        .values('job_id')
        .annotate(total=Sum('sale_amount'))
        .values('total')[:1]
    )
    last_paid_sq = (
        Payment.objects.filter(job_id=OuterRef('pk'))
        .order_by('-date', '-id')
        .values('date')[:1]
    )
    earliest_sale_date_sq = (
        Sale.objects.filter(job_id=OuterRef('pk'), sale_date__isnull=False)
        .order_by('sale_date', 'id')
        .values('sale_date')[:1]
    )
    earliest_co_date_sq = (
        ChangeOrder.objects.filter(job_id=OuterRef('pk'), order_date__isnull=False)
        .order_by('order_date', 'id')
        .values('order_date')[:1]
    )

    jobs = (
        Job.objects.filter(sold=True)
        .select_related('customer', 'soldby')
        .annotate(
            change_order_total=Coalesce(
                Subquery(
                    change_order_total_sq,
                    output_field=DecimalField(max_digits=19, decimal_places=2),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=19, decimal_places=2),
            ),
            contract_sales_total=Coalesce(
                Subquery(
                    contract_sales_total_sq,
                    output_field=DecimalField(max_digits=19, decimal_places=2),
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=19, decimal_places=2),
            ),
            last_paid=Subquery(last_paid_sq, output_field=DateField()),
            effective_sold_date=Coalesce(
                TruncDate('datesold'),
                Subquery(earliest_sale_date_sq, output_field=DateField()),
                Subquery(earliest_co_date_sq, output_field=DateField()),
            ),
        )
    )

    if user_filter.isdigit():
        jobs = jobs.filter(soldby_id=int(user_filter))
    else:
        user_filter = ''
    if start_date_obj:
        jobs = jobs.filter(effective_sold_date__gte=start_date_obj)
    if end_date_obj:
        jobs = jobs.filter(effective_sold_date__lte=end_date_obj)
    if search_query:
        jobs = jobs.filter(job_code__icontains=search_query)

    jobs = jobs.order_by(
        'soldby__first_name',
        'soldby__last_name',
        'soldby__username',
        'job_code',
    )

    grouped = OrderedDict()
    flat_rows = []
    for job in jobs:
        person = job.soldby
        key = person.id if person else 0
        if key not in grouped:
            grouped[key] = {
                'user': person,
                'jobs': [],
                'total_sold': Decimal('0.00'),
            }

        if job.saleamount is not None and job.saleamount != 0:
            sale_base = job.saleamount
        else:
            sale_base = job.contract_sales_total or Decimal('0.00')
        sold_amount = sale_base + (job.change_order_total or Decimal('0.00'))

        customer = job.customer
        if customer:
            customer_name = f'{customer.first_name or ""} {customer.last_name or ""}'.strip() or '-'
        else:
            customer_name = '-'

        if person:
            if person.first_name or person.last_name:
                sales_person_name = f'{person.first_name or ""} {person.last_name or ""}'.strip()
            else:
                sales_person_name = person.username
        else:
            sales_person_name = 'Unassigned'

        row = {
            'job': job,
            'job_code': job.job_code or '-',
            'last_paid': job.last_paid,
            'customer_name': customer_name,
            'sales_person_name': sales_person_name,
            'sold_amount': sold_amount,
        }
        grouped[key]['jobs'].append(row)
        grouped[key]['total_sold'] += sold_amount
        flat_rows.append(row)

    grouped_list = list(grouped.values())
    grand_total = sum((g['total_sold'] for g in grouped_list), Decimal('0.00'))
    total_jobs = len(flat_rows)

    return {
        'grouped_by_user': grouped_list,
        'flat_rows': flat_rows,
        'grand_total': grand_total,
        'total_jobs': total_jobs,
        'user_filter': user_filter,
        'users': all_users,
        'start_date': start_date,
        'end_date': end_date,
        'start_date_obj': start_date_obj,
        'end_date_obj': end_date_obj,
        'search_query': search_query,
    }
