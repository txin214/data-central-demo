"""
Reconcile the eight RPT Product_IDs that were not represented in the DB.

- Remap Mohawk legacy IDs (7268-7271 -> 7264-7267) where DB pricing matches the lower IDs.
- Import truly missing products (26390, 30139).
- Link MN-AD-RRP450 (id 31092) to RPT 35702 and sync fields.
- Skip duplicate part_no rows that already exist under another legacy ID (12493).
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from product.management.commands.import_product_rpt import Command as ImportCommand
from product.management.commands.sync_product_fields_from_rpt import Command as SyncCommand
from product.models import Product


class Command(BaseCommand):
    help = 'Reconcile RPT Product_IDs that were missing from the database.'

    LEGACY_REMAPS = [
        (50481, 7264),
        (50482, 7265),
        (50483, 7266),
        (50484, 7267),
    ]

    IMPORT_LEGACY_IDS = [26390, 30139]

    LINK_AND_SYNC = [
        (31092, 35702),
    ]

    DUPLICATE_SKIPS = [
        {
            'rpt_id': 12493,
            'part_no': 'K-10551-2BZ',
            'db_id': 42566,
            'existing_legacy_id': 3148,
            'reason': 'duplicate part_no; DB product matches RPT 3148',
        },
    ]

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
        rpt_path = options['rpt_file']
        if not os.path.isabs(rpt_path):
            rpt_path = os.path.join(os.getcwd(), rpt_path)

        if not os.path.exists(rpt_path):
            self.stdout.write(self.style.ERROR(f'File not found: {rpt_path}'))
            return

        dry_run = options['dry_run']
        importer = ImportCommand()
        syncer = SyncCommand()
        columns = importer._parse_columns(rpt_path)
        fk_cache = importer._build_fk_cache()
        rpt_rows = self._load_rpt_rows(rpt_path, columns)

        stats = {
            'remapped': 0,
            'imported': 0,
            'linked': 0,
            'skipped': 0,
        }

        self.stdout.write(self.style.SUCCESS('--- Legacy ID remaps (Mohawk) ---'))
        for product_id, new_legacy_id in self.LEGACY_REMAPS:
            stats['remapped'] += self._remap_legacy(
                product_id, new_legacy_id, rpt_rows, dry_run
            )

        self.stdout.write(self.style.SUCCESS('--- Import missing products ---'))
        for legacy_id in self.IMPORT_LEGACY_IDS:
            stats['imported'] += self._import_legacy_row(
                legacy_id, rpt_path, columns, importer, fk_cache, rpt_rows, dry_run
            )

        self.stdout.write(self.style.SUCCESS('--- Link and sync existing products ---'))
        for product_id, legacy_id in self.LINK_AND_SYNC:
            stats['linked'] += self._link_and_sync(
                product_id, legacy_id, importer, syncer, fk_cache, rpt_rows, dry_run
            )

        self.stdout.write(self.style.SUCCESS('--- Duplicate part_no (skipped) ---'))
        for item in self.DUPLICATE_SKIPS:
            stats['skipped'] += 1
            self.stdout.write(
                self.style.WARNING(
                    f"RPT {item['rpt_id']} {item['part_no']}: {item['reason']} "
                    f"(db id={item['db_id']}, legacy={item['existing_legacy_id']})"
                )
            )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('RECONCILE SUMMARY'))
        self.stdout.write(f"Legacy remapped: {stats['remapped']}")
        self.stdout.write(f"Imported: {stats['imported']}")
        self.stdout.write(f"Linked + synced: {stats['linked']}")
        self.stdout.write(f"Skipped (duplicate part_no): {stats['skipped']}")

        if not dry_run:
            self.stdout.write('\nRun report_rpt_sync_status to verify remaining gaps.')

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

    def _remap_legacy(self, product_id, new_legacy_id, rpt_rows, dry_run):
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            self.stdout.write(self.style.ERROR(f'Skip remap: id={product_id} not found'))
            return 0

        if new_legacy_id not in rpt_rows:
            self.stdout.write(
                self.style.ERROR(f'Skip remap id={product_id}: RPT {new_legacy_id} not found')
            )
            return 0

        owner = Product.objects.filter(legacy_product_id=new_legacy_id).exclude(pk=product_id).first()
        if owner:
            self.stdout.write(
                self.style.ERROR(
                    f'Skip remap id={product_id}: legacy {new_legacy_id} owned by id={owner.id}'
                )
            )
            return 0

        old_legacy = product.legacy_product_id
        if dry_run:
            self.stdout.write(
                f'Would remap id={product_id} {product.part_no}: '
                f'legacy {old_legacy} -> {new_legacy_id}'
            )
            return 1

        Product.objects.filter(pk=product_id).update(legacy_product_id=new_legacy_id)
        self.stdout.write(
            self.style.SUCCESS(
                f'Remapped id={product_id} {product.part_no}: legacy {old_legacy} -> {new_legacy_id}'
            )
        )
        return 1

    def _import_legacy_row(self, legacy_id, rpt_path, columns, importer, fk_cache, rpt_rows, dry_run):
        row = rpt_rows.get(legacy_id)
        if row is None:
            self.stdout.write(self.style.ERROR(f'Skip import: RPT {legacy_id} not found'))
            return 0

        part_no = importer._null_if_empty(row.get('PartNo'))
        description = importer._null_if_empty(row.get('Description'))

        if Product.objects.filter(legacy_product_id=legacy_id).exists():
            self.stdout.write(self.style.WARNING(f'Skip import: legacy {legacy_id} already in DB'))
            return 0
        if Product.objects.filter(part_no=part_no).exists():
            owner = Product.objects.get(part_no=part_no)
            self.stdout.write(
                self.style.WARNING(
                    f'Skip import legacy {legacy_id}: part {part_no!r} owned by id={owner.id}'
                )
            )
            return 0

        if dry_run:
            self.stdout.write(
                f'Would import legacy {legacy_id}: {part_no!r} - {description[:50]!r}'
            )
            return 1

        with transaction.atomic():
            product = importer._create_product(row, legacy_id, part_no, description, fk_cache)
            importer._apply_post_create_updates(product, row)

        self.stdout.write(
            self.style.SUCCESS(
                f'Imported legacy {legacy_id} as id={product.id}: {part_no!r}'
            )
        )
        return 1

    def _link_and_sync(self, product_id, legacy_id, importer, syncer, fk_cache, rpt_rows, dry_run):
        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            self.stdout.write(self.style.ERROR(f'Skip link: id={product_id} not found'))
            return 0

        row = rpt_rows.get(legacy_id)
        if row is None:
            self.stdout.write(self.style.ERROR(f'Skip link id={product_id}: RPT {legacy_id} not found'))
            return 0

        owner = Product.objects.filter(legacy_product_id=legacy_id).exclude(pk=product_id).first()
        if owner:
            self.stdout.write(
                self.style.ERROR(
                    f'Skip link id={product_id}: legacy {legacy_id} owned by id={owner.id}'
                )
            )
            return 0

        rpt_part = importer._null_if_empty(row.get('PartNo'))[:40]
        if product.part_no != rpt_part:
            conflict = Product.objects.filter(part_no=rpt_part).exclude(pk=product_id).first()
            if conflict:
                self.stdout.write(
                    self.style.ERROR(
                        f'Skip link id={product_id}: RPT part {rpt_part!r} owned by id={conflict.id}'
                    )
                )
                return 0

        fields = syncer._fields_from_row(importer, row, legacy_id, fk_cache)
        new_part = fields.pop('part_no')
        if new_part != product.part_no:
            part_owner = Product.objects.filter(part_no=new_part).exclude(pk=product_id).first()
            if part_owner:
                self.stdout.write(
                    self.style.ERROR(
                        f'Skip link id={product_id}: cannot set part {new_part!r} (id={part_owner.id})'
                    )
                )
                return 0
            fields['part_no'] = new_part

        if dry_run:
            self.stdout.write(
                f'Would link id={product_id} {product.part_no!r} -> legacy {legacy_id} '
                f'and sync {len(fields)} fields'
            )
            return 1

        with transaction.atomic():
            for attr, value in fields.items():
                setattr(product, attr, value)
            product.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Linked id={product_id} to legacy {legacy_id}: {product.part_no!r}'
            )
        )
        return 1
