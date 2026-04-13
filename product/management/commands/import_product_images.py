"""
Django management command to import product images from prod folder based on CSV Product_ID
"""
import os
import csv
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files import File
from product.models import Product, ProductImage


class Command(BaseCommand):
    help = 'Import product images from prod folder based on CSV Product_ID mapping'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing Product_ID and PartNo mapping'
        )
        parser.add_argument(
            '--prod-folder',
            type=str,
            default='prod',
            help='Path to the prod folder containing images (default: prod)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        prod_folder = options['prod_folder']
        dry_run = options['dry_run']

        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'CSV file not found: {csv_file_path}'))
            return

        if not os.path.exists(prod_folder):
            self.stdout.write(self.style.ERROR(f'Prod folder not found: {prod_folder}'))
            return

        # Read CSV and create mapping: Product_ID -> PartNo
        product_mapping = {}
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                product_id = row.get('Product_ID', '').strip()
                part_no = row.get('PartNo', '').strip()
                if product_id and part_no:
                    product_mapping[product_id] = part_no

        self.stdout.write(f'Found {len(product_mapping)} products in CSV')

        stats = {
            'processed': 0,
            'images_found': 0,
            'images_imported': 0,
            'products_not_found': 0,
            'images_not_found': 0,
            'errors': 0
        }

        # Process each product
        for product_id, part_no in product_mapping.items():
            stats['processed'] += 1
            
            # Find product in database
            try:
                product = Product.objects.get(part_no=part_no)
            except Product.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Product {part_no} (ID {product_id}) not found in DB - skipping'))
                stats['products_not_found'] += 1
                continue
            except Product.MultipleObjectsReturned:
                self.stdout.write(self.style.WARNING(f'Multiple products found for {part_no} (ID {product_id}) - skipping'))
                stats['errors'] += 1
                continue

            # Check if product already has images
            existing_images = ProductImage.objects.filter(product=product)
            if existing_images.exists():
                self.stdout.write(f'Product {part_no} already has {existing_images.count()} images - skipping')
                continue

            # Look for images in prod folder: {product_id}_200.jpg (primary) and {product_id}_800.jpg (secondary)
            primary_image_path = os.path.join(prod_folder, f'{product_id}_200.jpg')
            secondary_image_path = os.path.join(prod_folder, f'{product_id}_800.jpg')
            
            # Check if files exist
            if not os.path.exists(primary_image_path):
                primary_image_path = None
            if not os.path.exists(secondary_image_path):
                secondary_image_path = None

            if not primary_image_path and not secondary_image_path:
                if stats['processed'] % 10 == 0:
                    self.stdout.write(f'No images found for {part_no} (ID {product_id})')
                stats['images_not_found'] += 1
                continue

            stats['images_found'] += 1

            if dry_run:
                self.stdout.write(f'[DRY RUN] Would import for {part_no} (ID {product_id}):')
                if primary_image_path:
                    self.stdout.write(f'  Primary: {primary_image_path}')
                if secondary_image_path:
                    self.stdout.write(f'  Secondary: {secondary_image_path}')
                continue

            # Import primary image
            if primary_image_path:
                try:
                    with open(primary_image_path, 'rb') as f:
                        image_name = os.path.basename(primary_image_path)
                        product_image = ProductImage.objects.create(
                            product=product,
                            is_primary=True
                        )
                        product_image.image.save(image_name, File(f), save=True)
                        stats['images_imported'] += 1
                        self.stdout.write(f'Imported primary image for {part_no}: {image_name}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error importing primary image for {part_no}: {e}'))
                    stats['errors'] += 1

            # Import secondary image
            if secondary_image_path:
                try:
                    with open(secondary_image_path, 'rb') as f:
                        image_name = os.path.basename(secondary_image_path)
                        product_image = ProductImage.objects.create(
                            product=product,
                            is_primary=False
                        )
                        product_image.image.save(image_name, File(f), save=True)
                        stats['images_imported'] += 1
                        self.stdout.write(f'Imported secondary image for {part_no}: {image_name}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error importing secondary image for {part_no}: {e}'))
                    stats['errors'] += 1

            if stats['processed'] % 10 == 0:
                self.stdout.write(f'Processed {stats["processed"]} products...')

        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write('='*80)
        self.stdout.write(f'Products processed: {stats["processed"]}')
        self.stdout.write(f'Products with images found: {stats["images_found"]}')
        self.stdout.write(f'Images imported: {stats["images_imported"]}')
        self.stdout.write(f'Products not found in DB: {stats["products_not_found"]}')
        self.stdout.write(f'Products with no images: {stats["images_not_found"]}')
        self.stdout.write(f'Errors: {stats["errors"]}')

