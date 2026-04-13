"""
Django management command to migrate existing product images to UUID-based structure.
Structure: product_images/{uuid-first-2-chars}/{product-uuid}_{suffix}.jpg
"""
import os
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from product.models import ProductImage


class Command(BaseCommand):
    help = 'Migrate existing product images to UUID-based folder structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually migrating'
        )
        parser.add_argument(
            '--skip-missing',
            action='store_true',
            help='Skip images where the file is missing'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        skip_missing = options['skip_missing']
        
        self.stdout.write(self.style.SUCCESS('Starting product image migration...'))
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be moved'))
        
        # Get media root
        media_root = settings.MEDIA_ROOT
        
        # Get all product images
        images = ProductImage.objects.select_related('product').all()
        total = images.count()
        
        self.stdout.write(f'Found {total} product images to migrate')
        
        stats = {
            'processed': 0,
            'migrated': 0,
            'skipped_missing': 0,
            'errors': 0
        }
        
        for image in images:
            stats['processed'] += 1
            
            try:
                # Get current file path
                if not image.image:
                    self.stdout.write(self.style.WARNING(f'  Image {image.id}: No file associated'))
                    stats['skipped_missing'] += 1
                    continue
                
                old_path = image.image.path if hasattr(image.image, 'path') else None
                old_name = image.image.name
                
                # Check if file exists
                if old_path and not os.path.exists(old_path):
                    if skip_missing:
                        self.stdout.write(self.style.WARNING(f'  Image {image.id}: File not found at {old_path} - skipping'))
                        stats['skipped_missing'] += 1
                        continue
                    else:
                        self.stdout.write(self.style.ERROR(f'  Image {image.id}: File not found at {old_path}'))
                        stats['errors'] += 1
                        continue
                
                # Get product UUID
                if not hasattr(image.product, 'uuid') or not image.product.uuid:
                    self.stdout.write(self.style.ERROR(f'  Image {image.id}: Product {image.product.id} has no UUID'))
                    stats['errors'] += 1
                    continue
                
                product_uuid = image.product.uuid
                
                # Extract suffix from current filename
                # Example: "Product_images/12704_200.jpg" -> "200"
                filename = os.path.basename(old_name)
                if '_' in filename:
                    suffix = filename.rsplit('_', 1)[1]
                    # Remove extension
                    suffix = os.path.splitext(suffix)[0]
                else:
                    # If no underscore, use filename without extension
                    suffix = os.path.splitext(filename)[0]
                
                # Get file extension
                ext = os.path.splitext(filename)[1]
                
                # Get first 2 characters of UUID for folder grouping
                uuid_prefix = str(product_uuid)[:2]
                
                # Create new filename: {uuid}_{suffix}.{ext}
                new_filename = f"{product_uuid}_{suffix}{ext}"
                
                # Create new path: product_images/{uuid-prefix}/{new_filename}
                # Use forward slashes for Django compatibility (works on all platforms)
                new_relative_path = f'product_images/{uuid_prefix}/{new_filename}'
                new_full_path = os.path.join(media_root, 'product_images', uuid_prefix, new_filename)
                
                # Create directory if it doesn't exist
                new_dir = os.path.dirname(new_full_path)
                if not dry_run:
                    os.makedirs(new_dir, exist_ok=True)
                
                # Show what will be done
                if stats['processed'] % 100 == 0:
                    self.stdout.write(f'  Processing {stats["processed"]}/{total}...')
                
                if dry_run:
                    self.stdout.write(f'  Would move: {old_name} -> {new_relative_path}')
                else:
                    # Move/rename the file
                    if old_path and os.path.exists(old_path):
                        shutil.move(old_path, new_full_path)
                        
                        # Update the database record
                        image.image.name = new_relative_path
                        image.save(update_fields=['image'])
                        
                        stats['migrated'] += 1
                    else:
                        self.stdout.write(self.style.ERROR(f'  Image {image.id}: File not found'))
                        stats['errors'] += 1
                        continue
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error processing image {image.id}: {str(e)}'))
                stats['errors'] += 1
                continue
        
        # Print summary
        self.stdout.write(self.style.SUCCESS('\n=== Migration Summary ==='))
        self.stdout.write(f'Total processed: {stats["processed"]}')
        if not dry_run:
            self.stdout.write(f'Successfully migrated: {stats["migrated"]}')
        self.stdout.write(f'Skipped (missing files): {stats["skipped_missing"]}')
        self.stdout.write(f'Errors: {stats["errors"]}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a dry run. Run without --dry-run to actually migrate files.'))

