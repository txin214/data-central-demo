"""
Import products from a SQL Server fixed-width .rpt export (product1.rpt).

Skips rows when legacy Product_ID or part_no already exists in the database.
Ignores: componentlevel, GlassPattern, Picture, SurplusIsDirty.
"""
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pytz
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from product.models import (
    FaucetDrill,
    LeadTime,
    Manufacturer,
    Product,
    ProductCategory,
    ProductSubCategory1,
    ProductSubCategory2,
    Vendor,
)


class Command(BaseCommand):
    help = (
        'Import products from a SQL Server .rpt file. '
        'Skips existing legacy_product_id or part_no without overwriting.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'rpt_file',
            nargs='?',
            default='product1.rpt',
            help='Path to the .rpt file (default: product1.rpt in project root)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='Commit every N imported products (default: 200)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and report counts without writing to the database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Only process the first N data rows (0 = all)',
        )

    def handle(self, *args, **options):
        rpt_path = options['rpt_file']
        if not os.path.isabs(rpt_path):
            rpt_path = os.path.join(os.getcwd(), rpt_path)

        if not os.path.exists(rpt_path):
            self.stdout.write(self.style.ERROR(f'File not found: {rpt_path}'))
            return

        columns = self._parse_columns(rpt_path)
        self.stdout.write(self.style.SUCCESS(f'Parsed {len(columns)} columns from {rpt_path}'))

        existing_legacy_ids = set(
            Product.objects.exclude(legacy_product_id__isnull=True).values_list(
                'legacy_product_id', flat=True
            )
        )
        existing_part_nos = set(Product.objects.values_list('part_no', flat=True))

        fk_cache = self._build_fk_cache()

        stats = {
            'total': 0,
            'imported': 0,
            'skipped_legacy': 0,
            'skipped_part_no': 0,
            'skipped_invalid': 0,
            'errors': [],
        }

        dry_run = options['dry_run']
        limit = options['limit']
        batch_size = options['batch_size']
        batch_buffer = []

        with open(rpt_path, 'r', encoding='utf-8', errors='replace') as handle:
            handle.readline()  # header
            handle.readline()  # dashes

            for line_no, raw_line in enumerate(handle, start=3):
                line = raw_line.rstrip('\n\r')
                if not line.strip() or line.lstrip().startswith('('):
                    break

                if limit and stats['total'] >= limit:
                    break

                stats['total'] += 1
                row = self._slice_row(line, columns)

                legacy_id = self._to_int(row.get('Product_ID'))
                part_no = self._null_if_empty(row.get('PartNo'))
                description = self._null_if_empty(row.get('Description'))

                if legacy_id is None:
                    stats['skipped_invalid'] += 1
                    continue
                if not part_no or not description:
                    stats['skipped_invalid'] += 1
                    continue

                if legacy_id in existing_legacy_ids:
                    stats['skipped_legacy'] += 1
                    continue
                if part_no in existing_part_nos:
                    stats['skipped_part_no'] += 1
                    continue

                try:
                    if dry_run:
                        stats['imported'] += 1
                        existing_legacy_ids.add(legacy_id)
                        existing_part_nos.add(part_no)
                        continue

                    batch_buffer.append((row, legacy_id, part_no, description, line_no))
                    if len(batch_buffer) >= batch_size:
                        imported, created_keys = self._flush_batch(batch_buffer, fk_cache, stats)
                        stats['imported'] += imported
                        for key in created_keys:
                            existing_legacy_ids.add(key[0])
                            existing_part_nos.add(key[1])
                        batch_buffer.clear()
                        self.stdout.write(
                            f'  ... imported {stats["imported"]} so far (line {line_no})'
                        )

                except Exception as exc:
                    stats['errors'].append({
                        'line': line_no,
                        'legacy_id': legacy_id,
                        'part_no': part_no,
                        'error': str(exc),
                    })
                    if len(stats['errors']) <= 20:
                        self.stdout.write(
                            self.style.ERROR(
                                f'Line {line_no}: {part_no} (ID {legacy_id}) - {exc}'
                            )
                        )

        if batch_buffer and not dry_run:
            imported, created_keys = self._flush_batch(batch_buffer, fk_cache, stats)
            stats['imported'] += imported
            for key in created_keys:
                existing_legacy_ids.add(key[0])
                existing_part_nos.add(key[1])
            batch_buffer.clear()

        self._print_summary(stats, dry_run)

    def _flush_batch(self, batch_buffer, fk_cache, stats):
        imported = 0
        created_keys = []
        for row, legacy_id, part_no, description, line_no in batch_buffer:
            try:
                with transaction.atomic():
                    product = self._create_product(row, legacy_id, part_no, description, fk_cache)
                    self._apply_post_create_updates(product, row)
                imported += 1
                created_keys.append((legacy_id, part_no))
            except Exception as exc:
                stats['errors'].append({
                    'line': line_no,
                    'legacy_id': legacy_id,
                    'part_no': part_no,
                    'error': str(exc),
                })
                if len(stats['errors']) <= 20:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Line {line_no}: {part_no} (ID {legacy_id}) - {exc}'
                        )
                    )
        return imported, created_keys

    def _parse_columns(self, rpt_path):
        with open(rpt_path, 'r', encoding='utf-8', errors='replace') as handle:
            header = handle.readline().rstrip('\n\r')
            dashes = handle.readline().rstrip('\n\r')

        spans = []
        index = 0
        while index < len(dashes):
            if dashes[index] == '-':
                start = index
                while index < len(dashes) and dashes[index] == '-':
                    index += 1
                spans.append((start, index))
            else:
                index += 1

        return [(header[start:end].strip(), start, end) for start, end in spans]

    def _slice_row(self, line, columns):
        padded = line.ljust(columns[-1][2])
        return {name: padded[start:end] for name, start, end in columns}

    def _build_fk_cache(self):
        return {
            'categories': {obj.id: obj for obj in ProductCategory.objects.all()},
            'subcat1': {obj.id: obj for obj in ProductSubCategory1.objects.all()},
            'subcat2': {obj.id: obj for obj in ProductSubCategory2.objects.all()},
            'manufacturers': {obj.id: obj for obj in Manufacturer.objects.all()},
            'vendors': {obj.id: obj for obj in Vendor.objects.all()},
            'lead_times': {obj.id: obj for obj in LeadTime.objects.all()},
            'drills': {obj.id: obj for obj in FaucetDrill.objects.all()},
        }

    def _create_product(self, row, legacy_id, part_no, description, fk_cache):
        category = fk_cache['categories'].get(self._to_int(row.get('Category_id')))
        sub_category1 = None
        sub_category2 = None

        sub1_id = self._to_int(row.get('SubCategory1_id'))
        if sub1_id:
            candidate = fk_cache['subcat1'].get(sub1_id)
            if candidate and (not category or candidate.category_id == category.id):
                sub_category1 = candidate

        sub2_id = self._to_int(row.get('SubCategory2_id'))
        if sub2_id and sub_category1:
            candidate = fk_cache['subcat2'].get(sub2_id)
            if candidate and candidate.sub_category1_id == sub_category1.id:
                sub_category2 = candidate

        manufacturer = fk_cache['manufacturers'].get(self._to_int(row.get('Man_ID')))

        pref_vendor = None
        pref_vendor_id = self._to_int(row.get('PrefVendor_ID'))
        if pref_vendor_id:
            pref_vendor = fk_cache['vendors'].get(pref_vendor_id)

        alt_vendor = None
        alt_vendor_id = self._to_int(row.get('AltVendor_ID'))
        if alt_vendor_id:
            alt_vendor = fk_cache['vendors'].get(alt_vendor_id)

        unit_lead_time = fk_cache['lead_times'].get(self._to_int(row.get('UnitLeadTime_ID')))
        bulk_lead_time = fk_cache['lead_times'].get(self._to_int(row.get('BulkLeadTime_id')))
        drill = fk_cache['drills'].get(self._to_int(row.get('Drill_ID')))

        status_value = self._null_if_empty(row.get('Status')) or 'A'
        status = status_value.upper() == 'A'

        product = Product(
            legacy_product_id=legacy_id,
            category=category,
            sub_category1=sub_category1,
            sub_category2=sub_category2,
            manufacturer=manufacturer,
            part_no=part_no[:40],
            description=description[:80],
            pref_vendor=pref_vendor,
            alt_vendor=alt_vendor,
            width=self._to_decimal(row.get('Width')),
            height=self._to_decimal(row.get('Height')),
            depth=self._to_decimal(row.get('Depth')),
            drill=drill,
            min_order=self._to_int(row.get('MinOrder')),
            min_stock=self._to_int(row.get('MinStock')),
            unit_material_cost=self._to_decimal(row.get('UnitMaterialCost')),
            unit_lead_time=unit_lead_time,
            unit_labor_minutes=self._to_int(row.get('UnitLaborMinutes')),
            unit_labor_cost=self._to_decimal(row.get('UnitLaborCost')),
            unit_total_cost=self._to_decimal(row.get('UnitTotalCost')),
            bulk_material_cost=self._to_decimal(row.get('BulkMaterialCost')),
            bulk_qty=self._to_int(row.get('BulkQty')),
            bulk_lead_time=bulk_lead_time,
            bulk_labor_cost=self._to_decimal(row.get('BulkLaborCost')),
            bulk_total_cost=self._to_decimal(row.get('BulkTotalCost')),
            retail_sell=self._to_decimal(row.get('RetailSell')),
            builder_sell=self._to_decimal(row.get('BuilderSell')),
            surplus_sell=self._to_decimal(row.get('SurplusSell')),
            date_entered=self._parse_date(row.get('DateEntered')),
            date_updated=self._parse_date(row.get('DateUpdated')),
            status=status,
            unit_base_cost=self._to_decimal(row.get('UnitBaseCost')),
            unit_top_install_minutes=self._to_int(row.get('UnitTopInstallMinutes')),
        )
        product.save()
        return product

    def _apply_post_create_updates(self, product, row):
        """Restore CSV/RPT dates and optional text fields without re-triggering save()."""
        update_dict = {}
        date_entered = self._parse_date(row.get('DateEntered'))
        date_updated = self._parse_date(row.get('DateUpdated'))
        upc = self._null_if_empty(row.get('UPC'))
        product_lbl = self._null_if_empty(row.get('ProductLbl'))

        if date_entered:
            update_dict['date_entered'] = date_entered
        if date_updated:
            update_dict['date_updated'] = date_updated
        if upc:
            update_dict['upc'] = upc[:50]
        if product_lbl:
            update_dict['product_lbl'] = product_lbl[:50]

        if update_dict:
            Product.objects.filter(pk=product.pk).update(**update_dict)

    def _null_if_empty(self, value):
        if value is None:
            return None
        value = str(value).strip()
        if not value or value.upper() == 'NULL':
            return None
        return value

    def _to_decimal(self, value):
        value = self._null_if_empty(value)
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    def _to_int(self, value):
        value = self._null_if_empty(value)
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _parse_date(self, value):
        value = self._null_if_empty(value)
        if value is None:
            return None

        def normalize_date(match):
            year = match.group(1)
            month = match.group(2).zfill(2)
            day = match.group(3).zfill(2)
            time_part = match.group(4) if match.lastindex >= 4 else ''
            return f'{year}-{month}-{day}{time_part}'

        value = re.sub(
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})(\s+\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d+)?)?)?',
            normalize_date,
            value,
        )

        formats = [
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return timezone.make_aware(parsed, pytz.UTC)
            except ValueError:
                continue
        return None

    def _print_summary(self, stats, dry_run):
        self.stdout.write('\n' + '=' * 80)
        title = 'DRY RUN SUMMARY' if dry_run else 'IMPORT SUMMARY'
        self.stdout.write(self.style.SUCCESS(title))
        self.stdout.write('=' * 80)
        self.stdout.write(f"Data rows processed: {stats['total']}")
        self.stdout.write(self.style.SUCCESS(f"Would import / imported: {stats['imported']}"))
        self.stdout.write(self.style.WARNING(f"Skipped (existing legacy ID): {stats['skipped_legacy']}"))
        self.stdout.write(self.style.WARNING(f"Skipped (existing part no): {stats['skipped_part_no']}"))
        self.stdout.write(self.style.WARNING(f"Skipped (invalid row): {stats['skipped_invalid']}"))
        self.stdout.write(self.style.ERROR(f"Errors: {len(stats['errors'])}"))
        if stats['errors']:
            self.stdout.write('\nFirst errors:')
            for error in stats['errors'][:20]:
                self.stdout.write(
                    f"  Line {error['line']}: {error['part_no']} "
                    f"(legacy {error['legacy_id']}) - {error['error']}"
                )
