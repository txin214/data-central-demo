"""
Django management command to import products from CSV file
"""
import csv
import os
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.db import transaction
from product.models import (
    Product, ProductCategory, ProductSubCategory1, ProductSubCategory2,
    Manufacturer, Vendor, LeadTime
)


class Command(BaseCommand):
    help = 'Import products from CSV file. Skips products that already exist by part_no.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file to import'
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {csv_file_path}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Starting import from: {csv_file_path}'))
        
        # Track statistics
        stats = {
            'total': 0,
            'imported': 0,
            'skipped': [],
            'errors': []
        }

        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
                stats['total'] += 1
                part_no = row.get('PartNo', '').strip()
                
                if not part_no:
                    stats['errors'].append({
                        'row': row_num,
                        'part_no': 'MISSING',
                        'error': 'PartNo is required but was empty'
                    })
                    continue

                # Check if product already exists
                if Product.objects.filter(part_no=part_no).exists():
                    existing_product = Product.objects.get(part_no=part_no)
                    stats['skipped'].append({
                        'row': row_num,
                        'part_no': part_no,
                        'product_id': existing_product.id,
                        'description': existing_product.description
                    })
                    self.stdout.write(
                        self.style.WARNING(
                            f'Row {row_num}: Product {part_no} already exists (DB ID: {existing_product.id}) - SKIPPED'
                        )
                    )
                    continue

                # Try to import the product
                try:
                    with transaction.atomic():
                        product = self.create_product(row, row_num)
                        if product:
                            stats['imported'] += 1
                            csv_product_id = row.get('Product_ID', 'N/A')
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Row {row_num}: Imported {part_no} (CSV Product_ID: {csv_product_id})'
                                )
                            )
                except Exception as e:
                    stats['errors'].append({
                        'row': row_num,
                        'part_no': part_no,
                        'error': str(e)
                    })
                    self.stdout.write(
                        self.style.ERROR(
                            f'Row {row_num}: Error importing {part_no}: {str(e)}'
                        )
                    )

        # Print summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write('='*80)
        self.stdout.write(f'Total rows processed: {stats["total"]}')
        self.stdout.write(self.style.SUCCESS(f'Successfully imported: {stats["imported"]}'))
        self.stdout.write(self.style.WARNING(f'Skipped (already exist): {len(stats["skipped"])}'))
        self.stdout.write(self.style.ERROR(f'Errors: {len(stats["errors"])}'))
        
        if stats['skipped']:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.WARNING('PRODUCTS THAT ALREADY EXIST (NOT OVERWRITTEN):'))
            self.stdout.write('='*80)
            for skipped in stats['skipped']:
                self.stdout.write(
                    f"  Row {skipped['row']}: Part No: {skipped['part_no']} | "
                    f"DB ID: {skipped['product_id']} | "
                    f"Description: {skipped['description'][:50]}"
                )
        
        if stats['errors']:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.ERROR('ERRORS:'))
            self.stdout.write('='*80)
            for error in stats['errors']:
                self.stdout.write(
                    f"  Row {error['row']}: Part No: {error['part_no']} | Error: {error['error']}"
                )

    def create_product(self, row, row_num):
        """Create a Product instance from CSV row data"""
        
        # Helper function to convert NULL/empty to None
        def null_if_empty(value):
            if value is None or value == '' or str(value).strip().upper() == 'NULL':
                return None
            return str(value).strip()

        # Helper function to convert to Decimal
        def to_decimal(value):
            value = null_if_empty(value)
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError):
                return None

        # Helper function to convert to Integer
        def to_int(value):
            value = null_if_empty(value)
            if value is None:
                return None
            try:
                return int(float(value))  # Handle "0.00" -> 0
            except (ValueError, TypeError):
                return None

        # Helper function to parse datetime
        def parse_date(value):
            value = null_if_empty(value)
            if value is None:
                return None
            
            # Normalize single-digit months/days in format like "2005/10/3 11:53"
            import re
            # Convert "2005/10/3 11:53" to "2005/10/03 11:53"
            def normalize_date(match):
                year = match.group(1)
                month = match.group(2).zfill(2)  # Pad to 2 digits
                day = match.group(3).zfill(2)     # Pad to 2 digits
                time_part = match.group(4) if match.lastindex >= 4 else ''
                return f"{year}/{month}/{day}{time_part}"
            
            # Pattern: YYYY/M/D or YYYY/MM/D or YYYY/M/DD followed by optional time
            value = re.sub(r'(\d{4})/(\d{1,2})/(\d{1,2})(\s+\d{1,2}:\d{1,2}(?::\d{1,2})?)?', normalize_date, value)
            
            # Try different date formats
            formats = [
                '%Y-%m-%d %H:%M:%S.%f',
                '%Y-%m-%d %H:%M:%S',
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d %H:%M',
                '%Y/%m/%d',
                '%Y-%m-%d',
            ]
            for fmt in formats:
                try:
                    from datetime import datetime
                    from django.utils import timezone
                    import pytz
                    dt = datetime.strptime(value, fmt)
                    # Make timezone-aware in UTC to prevent Django from treating it as local time
                    return timezone.make_aware(dt, pytz.UTC)
                except ValueError:
                    continue
            return None

        # Get ForeignKey objects
        category = None
        if row.get('Category_id'):
            try:
                category = ProductCategory.objects.get(id=int(row['Category_id']))
            except (ProductCategory.DoesNotExist, ValueError):
                pass

        sub_category1 = None
        if row.get('SubCategory1_id') and category:
            try:
                sub_category1 = ProductSubCategory1.objects.get(
                    id=int(row['SubCategory1_id']),
                    category=category
                )
            except (ProductSubCategory1.DoesNotExist, ValueError):
                pass

        sub_category2 = None
        if row.get('SubCategory2_id') and sub_category1:
            try:
                sub_category2 = ProductSubCategory2.objects.get(
                    id=int(row['SubCategory2_id']),
                    sub_category1=sub_category1
                )
            except (ProductSubCategory2.DoesNotExist, ValueError):
                pass

        manufacturer = None
        if row.get('Man_ID'):
            try:
                manufacturer = Manufacturer.objects.get(id=int(row['Man_ID']))
            except (Manufacturer.DoesNotExist, ValueError):
                pass

        pref_vendor = None
        if row.get('PrefVendor_ID'):
            vendor_id = null_if_empty(row['PrefVendor_ID'])
            if vendor_id:
                try:
                    pref_vendor = Vendor.objects.get(id=int(vendor_id))
                except (Vendor.DoesNotExist, ValueError):
                    pass

        alt_vendor = None
        if row.get('AltVendor_ID'):
            vendor_id = null_if_empty(row['AltVendor_ID'])
            if vendor_id:
                try:
                    alt_vendor = Vendor.objects.get(id=int(vendor_id))
                except (Vendor.DoesNotExist, ValueError):
                    pass

        unit_lead_time = None
        if row.get('UnitLeadTime_ID'):
            try:
                unit_lead_time = LeadTime.objects.get(id=int(row['UnitLeadTime_ID']))
            except (LeadTime.DoesNotExist, ValueError):
                pass

        bulk_lead_time = None
        if row.get('BulkLeadTime_id'):
            lead_time_id = null_if_empty(row['BulkLeadTime_id'])
            if lead_time_id:
                try:
                    bulk_lead_time = LeadTime.objects.get(id=int(lead_time_id))
                except (LeadTime.DoesNotExist, ValueError):
                    pass

        # Convert Status: 'A' = True, 'I' = False, default = True
        status_value = null_if_empty(row.get('Status', 'A'))
        if status_value:
            status = status_value.upper() == 'A'
        else:
            status = True

        # Convert component_level
        component_level = to_int(row.get('componentlevel')) or 1
        if component_level not in [1, 2]:
            component_level = 1

        # Parse dates and optional fields from CSV before creating product
        csv_date_entered = parse_date(row.get('DateEntered'))
        csv_date_updated = parse_date(row.get('DateUpdated'))
        csv_upc = null_if_empty(row.get('UPC'))
        csv_product_lbl = null_if_empty(row.get('ProductLbl'))

        # Create the product
        product = Product(
            category=category,
            sub_category1=sub_category1,
            sub_category2=sub_category2,
            manufacturer=manufacturer,
            part_no=null_if_empty(row.get('PartNo')),
            description=null_if_empty(row.get('Description')) or '',
            pref_vendor=pref_vendor,
            alt_vendor=alt_vendor,
            width=to_decimal(row.get('Width')),
            height=to_decimal(row.get('Height')),
            depth=to_decimal(row.get('Depth')),
            min_order=to_int(row.get('MinOrder')),
            min_stock=to_int(row.get('MinStock')),
            unit_material_cost=to_decimal(row.get('UnitMaterialCost')),
            unit_lead_time=unit_lead_time,
            unit_labor_minutes=to_int(row.get('UnitLaborMinutes')),
            unit_labor_cost=to_decimal(row.get('UnitLaborCost')),
            unit_total_cost=to_decimal(row.get('UnitTotalCost')),
            bulk_material_cost=to_decimal(row.get('BulkMaterialCost')),
            bulk_qty=to_int(row.get('BulkQty')),
            bulk_lead_time=bulk_lead_time,
            bulk_labor_cost=to_decimal(row.get('BulkLaborCost')),
            bulk_total_cost=to_decimal(row.get('BulkTotalCost')),
            retail_sell=to_decimal(row.get('RetailSell')),
            builder_sell=to_decimal(row.get('BuilderSell')),
            surplus_sell=to_decimal(row.get('SurplusSell')),
            date_entered=csv_date_entered,
            date_updated=csv_date_updated,
            status=status,
            component_level=component_level,
            unit_base_cost=to_decimal(row.get('UnitBaseCost')),
            unit_top_install_minutes=to_int(row.get('UnitTopInstallMinutes')),
        )

        # Validate required fields
        if not product.part_no:
            raise ValueError("PartNo is required")
        if not product.description:
            raise ValueError("Description is required")

        # Save the product (this will set date_updated to now() due to model's save() method)
        product.save()
        
        # Update date_entered, date_updated, UPC, and product_lbl from CSV using QuerySet.update()
        # to bypass the model's save() method which auto-updates date_updated
        update_dict = {}
        if csv_date_entered:
            update_dict['date_entered'] = csv_date_entered
        if csv_date_updated:
            update_dict['date_updated'] = csv_date_updated
        if csv_upc:
            update_dict['upc'] = csv_upc
        if csv_product_lbl:
            update_dict['product_lbl'] = csv_product_lbl
        
        if update_dict:
            Product.objects.filter(id=product.id).update(**update_dict)
        
        return product

