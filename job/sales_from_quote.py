"""
Generate Sale rows from the job's primary product quote, grouped by ProductCategory.
Uses CategoryProductCodeMap when configured; otherwise falls back to DEFAULT_CATEGORY_NAME_TO_PC_CODE per category label.
Then ProductCode MX if still unresolved. SubCategory1ProductCodeMap overrides when all lines share one subcategory1.

Sale amounts include sales tax: each category pretax subtotal × county rate from
quote.get_tax_rate() (same basis as ProductQuote.calculate_tax).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction

from product.models import ProductCode, ProductCategory


# When CategoryProductCodeMap has no row: infer ProductCode by catalog category display name.
# Keys must match ProductCategory.product_category exactly (as used in quote group labels).
DEFAULT_CATEGORY_NAME_TO_PC_CODE: dict[str, str] = {
    "Appliances": "AP",
    "Bath Accessories": "BA",
    "Bath Featured Products": "BA",
    "Cabinets": "CK",
    "Ceramic Tile": "CR",
    "Closet Systems": "MX",
    "COUPONS": "DIS",
    "Delivery": "DEL",
    "Doors & Windows": "WP",
    "Flooring": "FL",
    "GENEVA CONDOS": "MX",
    "Hardware": "HD",
    "Labor": "SL",
    "Lake Geneva Condos": "MX",
    "Lighting & Electrical": "LV",
    "Plumbing Bath Faucets": "PFF",
    "Plumbing Bath Fixtures": "PFX",
    "Plumbing Kitchen Faucets": "PFF",
    "Plumbing Kitchen Fixtures": "PFX",
    "Product Category": "MX",
    "River Renaissance": "MX",
    "Sales & Promotions": "DIS",
    "Shower Products": "SS",
    "Site Materials": "MX",
    "Surplus Products": "DS",
    "Tops - Other": "CTQ",
    "Tops - Quartz": "CTQ",
    "Tops - Solid Surface": "CTS",
    "Trim & Doors": "WP",
    "Tub & Shower Doors": "PSD",
    "Vents & Heaters": "LV",
    "Z-On Line Products": "MX",
}


def infer_product_code_from_category_label(category_label: str | None) -> ProductCode | None:
    """Fallback ProductCode when admin maps are empty or incomplete."""
    if not category_label or category_label == "Uncategorized":
        return None
    label = " ".join(category_label.split())
    code_str = DEFAULT_CATEGORY_NAME_TO_PC_CODE.get(label)
    if not code_str:
        cf = label.casefold()
        for key, code in DEFAULT_CATEGORY_NAME_TO_PC_CODE.items():
            if key.casefold() == cf:
                code_str = code
                break
    if not code_str:
        return None
    return ProductCode.objects.filter(code=code_str).first()


def sale_line_comment(product_code, fallback: str = "") -> str:
    """Uppercase product description for sales/accounting comment column."""
    base = ""
    if product_code and getattr(product_code, "description", None):
        base = product_code.description
    elif fallback:
        base = fallback
    return base.strip().upper()


def aggregate_primary_quote_cost_by_category(quote) -> dict[int | None, Decimal]:
    """
    Sum extended cost (unit cost × qty) by ProductCategory id for catalog and ad-hoc lines.
    Uses Product.unit_total_cost and AdHoc.cost when present.
    """
    totals: defaultdict[int | None, Decimal] = defaultdict(lambda: Decimal("0"))

    for line in quote.line_items.select_related("product__category").all():
        cid = line.product.category_id
        uc = line.product.unit_total_cost
        unit = Decimal(uc) if uc is not None else Decimal("0")
        totals[cid] += unit * Decimal(line.quantity)

    for line in quote.adhoc_line_items.select_related("adhoc__category").all():
        cid = line.adhoc.category_id if line.adhoc else None
        ac = line.adhoc.cost if line.adhoc and line.adhoc.cost is not None else Decimal("0")
        totals[cid] += Decimal(ac) * Decimal(line.quantity)

    return dict(totals)


def aggregate_primary_quote_by_category(quote) -> dict[int | None, Decimal]:
    """
    Sum line totals by ProductCategory id. None = uncategorized (no product category on line).
    Includes catalog lines and ad-hoc lines (via AdHoc.category).
    """
    totals: defaultdict[int | None, Decimal] = defaultdict(lambda: Decimal("0"))

    for line in quote.line_items.select_related("product__category").all():
        cid = line.product.category_id
        totals[cid] += Decimal(line.total_price or 0)

    for line in quote.adhoc_line_items.select_related("adhoc__category").all():
        cid = line.adhoc.category_id if line.adhoc else None
        totals[cid] += Decimal(line.total_price or 0)

    return dict(totals)


def suggested_product_code_id_for_quote_lines(
    items,
    category_to_pc_id: dict,
    subcat1_to_pc_id: dict,
    category_label: str | None = None,
):
    """
    Return a ProductCode id for the job sales Quote table column when a map exists.
    Prefers SubCategory1 map when every line shares the same non-null sub_category1.
    Then tries ProductCategory map for every distinct category id in the group (lines
    can share the same display name but different ProductCategory rows).
    Finally tries ProductCategory rows whose name matches category_label (duplicate names).
    """
    if not items:
        return None
    sub1_ids = [line.product.sub_category1_id for line in items]
    if all(i is not None for i in sub1_ids) and len(set(sub1_ids)) == 1:
        sid = sub1_ids[0]
        pcid = subcat1_to_pc_id.get(sid)
        if pcid:
            return pcid
    cat_ids = [line.product.category_id for line in items]
    unique_cat = {x for x in cat_ids if x is not None}
    for cid in unique_cat:
        pcid = category_to_pc_id.get(cid)
        if pcid:
            return pcid
    if category_label:
        from product.models import ProductCategory

        for pcat in ProductCategory.objects.filter(product_category=category_label):
            pcid = category_to_pc_id.get(pcat.id)
            if pcid:
                return pcid
    inferred = infer_product_code_from_category_label(category_label)
    if inferred:
        return inferred.pk
    return None


def _default_misc_code():
    return ProductCode.objects.filter(code="MX").first()


def generate_sales_from_primary_quote(job, user) -> dict:
    """
    Delete existing Sale rows for this job that were generated from the same primary quote,
    then create new Sale rows (one per category bucket with nonzero total).

    Returns dict: success, created (int), error (optional str).
    """
    from .models import CategoryProductCodeMap, Sale

    quote = job.product_quotes.filter(is_primary=True).first()
    if not quote:
        return {"success": False, "error": "No primary product quote for this job."}

    totals = aggregate_primary_quote_by_category(quote)
    if not totals or all(a == 0 for a in totals.values()):
        return {"success": False, "error": "Primary quote has no line items with a total."}

    code_by_category = {
        m.product_category_id: m.product_code
        for m in CategoryProductCodeMap.objects.select_related("product_code")
    }
    mx = _default_misc_code()
    created = 0
    today = job.datesold.date() if job.datesold else date.today()
    tax_rate = quote.get_tax_rate()
    cost_totals = aggregate_primary_quote_cost_by_category(quote)

    with transaction.atomic():
        Sale.objects.filter(job=job, source_quote=quote).delete()

        for category_id, subtotal in totals.items():
            if subtotal == 0:
                continue
            subtotal = subtotal.quantize(Decimal("0.01"))
            if subtotal == 0:
                continue

            # Same basis as ProductQuote.calculate_tax(): county rate × pretax subtotal.
            tax_part = (subtotal * tax_rate).quantize(Decimal("0.01"))
            amount = (subtotal + tax_part).quantize(Decimal("0.01"))
            cost_part = cost_totals.get(category_id, Decimal("0")).quantize(Decimal("0.01"))

            product_code = None
            label = "Uncategorized"
            if category_id is not None:
                product_code = code_by_category.get(category_id)
                try:
                    label = ProductCategory.objects.get(pk=category_id).product_category
                except ProductCategory.DoesNotExist:
                    label = "Unknown category"
                if product_code is None:
                    product_code = infer_product_code_from_category_label(label)
            if product_code is None:
                product_code = mx

            comment = sale_line_comment(product_code, label)

            Sale.objects.create(
                job=job,
                source_quote=quote,
                product_code=product_code,
                cost_amount=cost_part,
                tax_amount=tax_part,
                sale_amount=amount,
                sale_date=today,
                tax="UT",
                comment=comment,
                created_by=user if user and user.is_authenticated else None,
            )
            created += 1

    return {"success": True, "created": created}


def _primary_product_quote(job):
    return job.product_quotes.filter(is_primary=True).first()


def _primary_sitework_quote(job):
    sw = job.sitework_quotes.filter(is_primary=True).first()
    if not sw:
        sw = job.sitework_quotes.order_by("-id").first()
    return sw


def _job_tax_rate(job) -> Decimal:
    quote = _primary_product_quote(job)
    if quote:
        return quote.get_tax_rate()
    if job.county_id and job.county.taxrate is not None:
        return Decimal(str(job.county.taxrate))
    return Decimal("0")


def compute_sitework_sale_amounts(job, tax_rate: Decimal | None = None) -> dict | None:
    """
    Sitework SL sale basis: category subtotals + 5% contingency + 28% overhead.
    Sitework is not taxed for accounting/sales.
    Returns None when there is no priced sitework.
    """
    from .utils import group_sitework_by_category

    primary_sw = _primary_sitework_quote(job)
    if not primary_sw:
        return None

    categories_data = group_sitework_by_category(primary_sw)
    sitework_subtotal = Decimal("0")
    for category in categories_data:
        subtotal_str = category["subtotal"].replace("$", "").replace(",", "")
        try:
            sitework_subtotal += Decimal(subtotal_str)
        except (ValueError, TypeError):
            pass

    if sitework_subtotal <= 0:
        return None

    contingency_pct = Decimal("0.05")
    overhead_pct = Decimal("0.28")
    contingency = sitework_subtotal * contingency_pct
    overhead = sitework_subtotal * overhead_pct
    sitework_total = (sitework_subtotal + contingency + overhead).quantize(Decimal("0.01"))

    return {
        "subtotal": sitework_subtotal.quantize(Decimal("0.01")),
        "total": sitework_total,
        "tax": Decimal("0.00"),
        "sale_total": sitework_total,
        "tax_rate": Decimal("0"),
    }


def generate_sitework_sale_from_primary_quote(job, user) -> dict:
    """Create or refresh the SL sale row from the primary sitework quote."""
    from product.models import ProductCode

    from .models import Sale

    amounts = compute_sitework_sale_amounts(job)
    if not amounts:
        return {"success": False, "error": "No priced sitework for this job."}

    sl = ProductCode.objects.filter(code="SL").first()
    if not sl:
        return {"success": False, "error": "Product code SL is not configured."}

    sale_date = job.datesold.date() if job.datesold else date.today()
    comment = sale_line_comment(sl, "Site Work")

    with transaction.atomic():
        Sale.objects.filter(job=job, product_code=sl).delete()
        Sale.objects.create(
            job=job,
            product_code=sl,
            cost_amount=amounts["subtotal"],
            tax_amount=Decimal("0.00"),
            sale_amount=amounts["sale_total"],
            sale_date=sale_date,
            tax="EX",
            comment=comment,
            created_by=user if user and getattr(user, "is_authenticated", False) else None,
        )

    return {"success": True, "created": 1}


def sync_sales_when_job_sold(job, user) -> dict:
    """
    When a job is sold, populate Sales from the primary product quote and sitework,
    then create SLW billing milestones. Skips quote/sitework generation if non-SLW
    sales already exist (manual Save Sales). Billing schedule sync is always attempted.
    """
    from django.db.models import Q

    from .billing_schedule import SLW_CODE, ensure_reverse_wip_amount, sync_billing_schedule_sales

    if not job.sold:
        return {"skipped": "not_sold"}

    result: dict = {}
    has_product_sales = job.sales.filter(~Q(product_code__code=SLW_CODE)).exists()

    if not has_product_sales:
        result["quote"] = generate_sales_from_primary_quote(job, user)
        result["sitework"] = generate_sitework_sale_from_primary_quote(job, user)

    result["billing"] = sync_billing_schedule_sales(job, created_by=user)
    if ensure_reverse_wip_amount(job):
        result["reverse_wip_corrected"] = True
    return result
