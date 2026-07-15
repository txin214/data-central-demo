"""SLW billing milestone rows when a job is marked sold."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum

from .models import Job, Sale

BILLING_SCHEDULE_MARKER = 'REVERSE WIP'
SLW_CODE = 'SLW'
UNDER_10K_THRESHOLD = Decimal('10000')


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal('0.01'))


def pct_of_total(total: Decimal, percent: int | float) -> Decimal:
    return _quantize(total * Decimal(str(percent)) / Decimal('100'))


def contract_total_for_job(job: Job) -> Decimal:
    """Contract amount from non-SLW sales, else job.saleamount."""
    total = (
        job.sales.filter(~Q(product_code__code=SLW_CODE))
        .aggregate(s=Sum('sale_amount'))['s']
        or Decimal('0')
    )
    if total > 0:
        return _quantize(Decimal(total))
    if job.saleamount is not None and job.saleamount > 0:
        return _quantize(Decimal(job.saleamount))
    return Decimal('0.00')


def has_billing_schedule(job: Job) -> bool:
    return job.sales.filter(
        product_code__code=SLW_CODE,
        comment__iexact=BILLING_SCHEDULE_MARKER,
    ).exists()


def build_billing_schedule_lines(contract_total: Decimal) -> list[dict]:
    """
    Return milestone rows (comment + amount). Always includes REVERSE WIP
    as a negative amount equal to the contract total.

    Under $10,000: 75% Deposit, 25% Completion
    $10,000 and up: 40% Deposit, 20% Start, 20% Rough, 15% Functional, 5% Punch
    """
    total = _quantize(Decimal(contract_total))
    if total <= 0:
        return []

    lines: list[tuple[str, Decimal]] = []

    if total < UNDER_10K_THRESHOLD:
        lines.append(('Deposit', pct_of_total(total, 75)))
        lines.append(('Completion', pct_of_total(total, 25)))
    else:
        lines.append(('Deposit', pct_of_total(total, 40)))
        lines.append(('Start', pct_of_total(total, 20)))
        lines.append(('Rough', pct_of_total(total, 20)))
        lines.append(('Functional', pct_of_total(total, 15)))
        lines.append(('Punch', pct_of_total(total, 5)))

    lines.append((BILLING_SCHEDULE_MARKER, -total))

    return [{'comment': comment, 'amount': amount} for comment, amount in lines]


def sync_billing_schedule_sales(job: Job, *, created_by=None) -> dict:
    """
    Create SLW milestone + REVERSE WIP sale rows when job is sold.
    Idempotent: skips if schedule already exists or contract total is zero.
    """
    if not job.sold:
        return {'created': 0, 'reason': 'not_sold'}

    if has_billing_schedule(job):
        return {'created': 0, 'reason': 'already_exists'}

    contract_total = contract_total_for_job(job)
    if contract_total <= 0:
        return {'created': 0, 'reason': 'no_contract_total'}

    from product.models import ProductCode

    slw = ProductCode.objects.filter(code=SLW_CODE).first()
    if not slw:
        return {'created': 0, 'reason': 'missing_slw_product_code'}

    schedule_lines = build_billing_schedule_lines(contract_total)
    if not schedule_lines:
        return {'created': 0, 'reason': 'no_lines'}

    sale_date = job.datesold.date() if job.datesold else date.today()
    created_ids = []
    for line in schedule_lines:
        sale = Sale.objects.create(
            job=job,
            product_code=slw,
            sale_amount=line['amount'],
            comment=line['comment'].upper(),
            sale_date=sale_date,
            tax='UT',
            created_by=created_by if getattr(created_by, 'is_authenticated', False) else None,
        )
        created_ids.append(sale.id)

    return {
        'created': len(created_ids),
        'sale_ids': created_ids,
        'contract_total': str(contract_total),
        'under_10k': contract_total < UNDER_10K_THRESHOLD,
    }


def ensure_reverse_wip_amount(job: Job) -> bool:
    """
    REVERSE WIP must be negative and equal to the contract total (non-SLW sales).
    Corrects legacy rows that were stored as positive. Returns True if updated.
    """
    rw = job.sales.filter(
        product_code__code=SLW_CODE,
        comment__iexact=BILLING_SCHEDULE_MARKER,
    ).first()
    if not rw:
        return False

    contract_total = contract_total_for_job(job)
    if contract_total <= 0:
        return False

    target = -contract_total
    if rw.sale_amount == target:
        return False

    rw.sale_amount = target
    rw.save(update_fields=['sale_amount', 'updated_at'])
    return True
