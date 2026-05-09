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
    today = date.today()
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

            if tax_rate > 0:
                comment = (
                    f"Generated from primary quote #{quote.id} — {label} "
                    f"(incl. tax at {tax_rate * 100:.2f}% on ${subtotal:.2f} pretax)"
                )
            else:
                comment = f"Generated from primary quote #{quote.id} — {label}"

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
