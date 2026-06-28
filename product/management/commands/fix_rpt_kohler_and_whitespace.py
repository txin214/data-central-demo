"""Fix Kohler K-45212 part numbers and strip trailing whitespace from descriptions."""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from product.management.commands.import_product_rpt import Command as ImportCommand
from product.models import Product


class Command(BaseCommand):
    help = 'Rename Kohler K-45212 part numbers and align descriptions with stripped RPT text.'

    def add_arguments(self, parser):
        parser.add_argument(
            'rpt_file',
            nargs='?',
            default='product1.rpt',
            help='Path to product1.rpt (default: product1.rpt)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report changes without saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        kohler_stats = self._fix_kohler_part_numbers(dry_run)
        whitespace_stats = self._strip_whitespace_descriptions(options['rpt_file'], dry_run)

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('FIX SUMMARY'))
        self.stdout.write(f"Kohler renames: {kohler_stats['renamed']}")
        self.stdout.write(f"Descriptions stripped: {whitespace_stats['stripped']}")
        if kohler_stats['skipped']:
            self.stdout.write(self.style.WARNING(f"Kohler skipped: {kohler_stats['skipped']}"))
        if whitespace_stats['skipped_part_diff']:
            self.stdout.write(
                self.style.WARNING(
                    f"Whitespace pass skipped (part still differs): {whitespace_stats['skipped_part_diff']}"
                )
            )

    def _fix_kohler_part_numbers(self, dry_run):
        """Rename in order: BN -> CP first, then BN1 -> BN."""
        renames = [
            (44513, 'K-45212-BN', 'K-45212-CP'),
            (45603, 'K-45212-BN1', 'K-45212-BN'),
        ]
        stats = {'renamed': 0, 'skipped': 0}

        for product_id, expected_old, new_part in renames:
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                stats['skipped'] += 1
                self.stdout.write(self.style.WARNING(f'Skip id={product_id}: not found'))
                continue

            if product.part_no != expected_old:
                stats['skipped'] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Skip id={product_id}: expected {expected_old!r}, found {product.part_no!r}'
                    )
                )
                continue

            if Product.objects.filter(part_no=new_part).exclude(pk=product_id).exists():
                owner = Product.objects.get(part_no=new_part)
                stats['skipped'] += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Skip id={product_id}: {new_part!r} already owned by id={owner.id}'
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    f'Would rename id={product_id}: {expected_old!r} -> {new_part!r}'
                )
            else:
                product.part_no = new_part
                product.save(update_fields=['part_no'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Renamed id={product_id}: {expected_old!r} -> {new_part!r}'
                    )
                )
            stats['renamed'] += 1

        return stats

    def _strip_whitespace_descriptions(self, rpt_file, dry_run):
        rpt_path = rpt_file
        if not os.path.isabs(rpt_path):
            rpt_path = os.path.join(os.getcwd(), rpt_path)

        importer = ImportCommand()
        columns = importer._parse_columns(rpt_path)
        rpt_by_id = {}

        with open(rpt_path, 'r', encoding='utf-8', errors='replace') as handle:
            handle.readline()
            handle.readline()
            for line in handle:
                line = line.rstrip('\n\r')
                if not line.strip() or line.lstrip().startswith('('):
                    break
                legacy_id = int(line[0:11].strip())
                padded = line.ljust(columns[-1][2])
                row = {name: padded[start:end] for name, start, end in columns}
                part_no = importer._null_if_empty(row.get('PartNo'))
                description = importer._null_if_empty(row.get('Description'))
                if part_no and description:
                    rpt_by_id[legacy_id] = {
                        'part_no': part_no[:40],
                        'description': description.strip()[:80],
                    }

        stats = {'stripped': 0, 'skipped_part_diff': 0}
        updates = []

        for product in Product.objects.exclude(legacy_product_id__isnull=True).iterator(chunk_size=5000):
            rpt_row = rpt_by_id.get(product.legacy_product_id)
            if rpt_row is None:
                continue

            if product.part_no != rpt_row['part_no']:
                stats['skipped_part_diff'] += 1
                continue

            new_desc = rpt_row['description']
            if product.description == new_desc:
                continue
            if (product.description or '').strip() != new_desc:
                continue

            updates.append((product.id, product.description, new_desc))

        if dry_run:
            stats['stripped'] = len(updates)
            for product_id, old_desc, new_desc in updates[:5]:
                self.stdout.write(
                    f'Would strip id={product_id}: {old_desc[-20:]!r} -> {new_desc[-20:]!r}'
                )
            if len(updates) > 5:
                self.stdout.write(f'  ... and {len(updates) - 5} more')
        else:
            with transaction.atomic():
                for product_id, old_desc, new_desc in updates:
                    Product.objects.filter(pk=product_id).update(description=new_desc)
                    stats['stripped'] += 1
            self.stdout.write(
                self.style.SUCCESS(f'Stripped trailing whitespace on {stats["stripped"]} descriptions')
            )

        return stats
