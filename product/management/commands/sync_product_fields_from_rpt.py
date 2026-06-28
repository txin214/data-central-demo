"""
Update existing products from product1.rpt using legacy_product_id.

Intended for products whose legacy ID already matches RPT but part_no/description
(or other fields) differ. By default reads db_id values from legacy_id_differs_from_rpt.csv.
"""
import csv
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from product.management.commands.import_product_rpt import Command as ImportCommand
from product.models import Product


class Command(BaseCommand):
    help = (
        'Update product fields from product1.rpt for rows linked by legacy_product_id. '
        'Skips part_no changes when another product already owns the RPT part number.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'rpt_file',
            nargs='?',
            default='product1.rpt',
            help='Path to the .rpt file (default: product1.rpt)',
        )
        parser.add_argument(
            '--csv',
            default='legacy_id_differs_from_rpt.csv',
            help='CSV with db_id column listing products to update (default: legacy_id_differs_from_rpt.csv)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report changes without saving',
        )

    def handle(self, *args, **options):
        rpt_path = options['rpt_file']
        if not os.path.isabs(rpt_path):
            rpt_path = os.path.join(os.getcwd(), rpt_path)

        if not os.path.exists(rpt_path):
            self.stdout.write(self.style.ERROR(f'File not found: {rpt_path}'))
            return

        csv_path = options['csv']
        if csv_path and not os.path.isabs(csv_path):
            csv_path = os.path.join(os.getcwd(), csv_path)

        product_ids = self._load_product_ids(csv_path)
        if not product_ids:
            self.stdout.write(self.style.ERROR('No product IDs to update.'))
            return

        importer = ImportCommand()
        columns = importer._parse_columns(rpt_path)
        fk_cache = importer._build_fk_cache()
        rpt_by_id = self._load_rpt_rows(rpt_path, columns)

        part_owner = dict(Product.objects.values_list('part_no', 'id'))
        products = {
            p.id: p
            for p in Product.objects.filter(id__in=product_ids).select_related(
                'category',
                'sub_category1',
                'sub_category2',
                'manufacturer',
                'pref_vendor',
                'alt_vendor',
                'unit_lead_time',
                'bulk_lead_time',
                'drill',
            )
        }

        stats = {
            'updated': 0,
            'skipped_missing_product': 0,
            'skipped_missing_rpt': 0,
            'skipped_no_legacy': 0,
            'part_no_skipped': 0,
        }
        updates = []

        for product_id in product_ids:
            product = products.get(product_id)
            if product is None:
                stats['skipped_missing_product'] += 1
                continue

            legacy_id = product.legacy_product_id
            if legacy_id is None:
                stats['skipped_no_legacy'] += 1
                continue

            row = rpt_by_id.get(legacy_id)
            if row is None:
                stats['skipped_missing_rpt'] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Skip id={product_id}: no RPT row for legacy {legacy_id}'
                    )
                )
                continue

            fields = self._fields_from_row(importer, row, legacy_id, fk_cache)
            new_part = fields.pop('part_no')
            skip_part_no = False
            if new_part != product.part_no:
                owner = part_owner.get(new_part)
                if owner is not None and owner != product.id:
                    skip_part_no = True
                    stats['part_no_skipped'] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skip part_no for id={product_id}: {product.part_no} -> {new_part} '
                            f'(owned by id={owner}); updating other fields'
                        )
                    )
                else:
                    if product.part_no in part_owner:
                        del part_owner[product.part_no]
                    part_owner[new_part] = product.id
                    fields['part_no'] = new_part

            changed = self._changed_fields(product, fields)
            if skip_part_no and not changed:
                continue

            updates.append((product, fields, skip_part_no, new_part))

        dry_run = options['dry_run']
        if dry_run:
            stats['updated'] = len(updates)
            for product, fields, skip_part_no, new_part in updates:
                parts = []
                if not skip_part_no and product.part_no != new_part:
                    parts.append(f'part_no {product.part_no!r} -> {new_part!r}')
                if product.description != fields.get('description'):
                    parts.append('description')
                other = [k for k in fields if k not in ('part_no', 'description')]
                if other:
                    parts.append(f'{len(other)} other fields')
                self.stdout.write(
                    f'Would update id={product.id} legacy={product.legacy_product_id}: {", ".join(parts) or "fields"}'
                )
        else:
            with transaction.atomic():
                for product, fields, skip_part_no, new_part in updates:
                    for attr, value in fields.items():
                        setattr(product, attr, value)
                    product.save()
                    stats['updated'] += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Updated id={product.id} legacy={product.legacy_product_id}'
                            + (f' part_no={new_part}' if not skip_part_no and product.part_no == new_part else '')
                        )
                    )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('SYNC SUMMARY'))
        self.stdout.write(f"Products in CSV: {len(product_ids)}")
        self.stdout.write(f"Updated: {stats['updated']}")
        self.stdout.write(f"Part no skipped (conflict): {stats['part_no_skipped']}")
        self.stdout.write(f"Missing product: {stats['skipped_missing_product']}")
        self.stdout.write(f"Missing RPT row: {stats['skipped_missing_rpt']}")
        self.stdout.write(f"No legacy_product_id: {stats['skipped_no_legacy']}")

    def _load_product_ids(self, csv_path):
        if not csv_path or not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f'CSV not found: {csv_path}'))
            return []

        ids = []
        with open(csv_path, encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                db_id = row.get('db_id', '').strip()
                if db_id:
                    ids.append(int(db_id))
        return ids

    def _load_rpt_rows(self, rpt_path, columns):
        rows = {}
        with open(rpt_path, 'r', encoding='utf-8', errors='replace') as handle:
            handle.readline()
            handle.readline()
            for line in handle:
                line = line.rstrip('\n\r')
                if not line.strip() or line.lstrip().startswith('('):
                    break
                legacy_id = int(line[0:11].strip())
                padded = line.ljust(columns[-1][2])
                rows[legacy_id] = {
                    name: padded[start:end]
                    for name, start, end in columns
                }
        return rows

    def _fields_from_row(self, importer, row, legacy_id, fk_cache):
        part_no = importer._null_if_empty(row.get('PartNo'))
        description = importer._null_if_empty(row.get('Description'))

        category = fk_cache['categories'].get(importer._to_int(row.get('Category_id')))
        sub_category1 = None
        sub_category2 = None

        sub1_id = importer._to_int(row.get('SubCategory1_id'))
        if sub1_id:
            candidate = fk_cache['subcat1'].get(sub1_id)
            if candidate and (not category or candidate.category_id == category.id):
                sub_category1 = candidate

        sub2_id = importer._to_int(row.get('SubCategory2_id'))
        if sub2_id and sub_category1:
            candidate = fk_cache['subcat2'].get(sub2_id)
            if candidate and candidate.sub_category1_id == sub_category1.id:
                sub_category2 = candidate

        manufacturer = fk_cache['manufacturers'].get(importer._to_int(row.get('Man_ID')))

        pref_vendor = None
        pref_vendor_id = importer._to_int(row.get('PrefVendor_ID'))
        if pref_vendor_id:
            pref_vendor = fk_cache['vendors'].get(pref_vendor_id)

        alt_vendor = None
        alt_vendor_id = importer._to_int(row.get('AltVendor_ID'))
        if alt_vendor_id:
            alt_vendor = fk_cache['vendors'].get(alt_vendor_id)

        unit_lead_time = fk_cache['lead_times'].get(importer._to_int(row.get('UnitLeadTime_ID')))
        bulk_lead_time = fk_cache['lead_times'].get(importer._to_int(row.get('BulkLeadTime_id')))
        drill = fk_cache['drills'].get(importer._to_int(row.get('Drill_ID')))

        status_value = importer._null_if_empty(row.get('Status')) or 'A'
        status = status_value.upper() == 'A'

        fields = {
            'legacy_product_id': legacy_id,
            'category': category,
            'sub_category1': sub_category1,
            'sub_category2': sub_category2,
            'manufacturer': manufacturer,
            'part_no': part_no[:40] if part_no else None,
            'description': description[:80] if description else None,
            'pref_vendor': pref_vendor,
            'alt_vendor': alt_vendor,
            'width': importer._to_decimal(row.get('Width')),
            'height': importer._to_decimal(row.get('Height')),
            'depth': importer._to_decimal(row.get('Depth')),
            'drill': drill,
            'min_order': importer._to_int(row.get('MinOrder')),
            'min_stock': importer._to_int(row.get('MinStock')),
            'unit_material_cost': importer._to_decimal(row.get('UnitMaterialCost')),
            'unit_lead_time': unit_lead_time,
            'unit_labor_minutes': importer._to_int(row.get('UnitLaborMinutes')),
            'unit_labor_cost': importer._to_decimal(row.get('UnitLaborCost')),
            'unit_total_cost': importer._to_decimal(row.get('UnitTotalCost')),
            'bulk_material_cost': importer._to_decimal(row.get('BulkMaterialCost')),
            'bulk_qty': importer._to_int(row.get('BulkQty')),
            'bulk_lead_time': bulk_lead_time,
            'bulk_labor_cost': importer._to_decimal(row.get('BulkLaborCost')),
            'bulk_total_cost': importer._to_decimal(row.get('BulkTotalCost')),
            'retail_sell': importer._to_decimal(row.get('RetailSell')),
            'builder_sell': importer._to_decimal(row.get('BuilderSell')),
            'surplus_sell': importer._to_decimal(row.get('SurplusSell')),
            'date_entered': importer._parse_date(row.get('DateEntered')),
            'date_updated': importer._parse_date(row.get('DateUpdated')),
            'status': status,
            'unit_base_cost': importer._to_decimal(row.get('UnitBaseCost')),
            'unit_top_install_minutes': importer._to_int(row.get('UnitTopInstallMinutes')),
        }

        upc = importer._null_if_empty(row.get('UPC'))
        product_lbl = importer._null_if_empty(row.get('ProductLbl'))
        if upc:
            fields['upc'] = upc[:50]
        else:
            fields['upc'] = None
        if product_lbl:
            fields['product_lbl'] = product_lbl[:50]
        else:
            fields['product_lbl'] = None

        return fields

    def _changed_fields(self, product, fields):
        changed = {}
        for attr, value in fields.items():
            current = getattr(product, attr)
            if self._field_changed(current, value):
                changed[attr] = value
        return changed

    def _field_changed(self, current, new):
        if current is None and new is None:
            return False
        if hasattr(current, 'pk'):
            current_pk = current.pk if current else None
            new_pk = new.pk if new else None
            return current_pk != new_pk
        if hasattr(current, 'quantize'):
            if new is None:
                return True
            return current != new
        return current != new
