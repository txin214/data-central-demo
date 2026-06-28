"""
Set legacy_product_id from product1.rpt by matching part_no + description.
Does not change part_no, description, or other fields.
"""
import os
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from product.models import Product


class Command(BaseCommand):
    help = 'Update legacy_product_id to match RPT Product_ID using part_no + description.'

    def add_arguments(self, parser):
        parser.add_argument(
            'rpt_file',
            nargs='?',
            default='product1.rpt',
            help='Path to the .rpt file (default: product1.rpt)',
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

        rpt_by_key, ambiguous = self._load_rpt(rpt_path)
        legacy_owner = {
            p.legacy_product_id: p.id
            for p in Product.objects.exclude(legacy_product_id__isnull=True)
        }

        stats = {
            'already_ok': 0,
            'updated': 0,
            'no_match': 0,
            'skipped_conflict': 0,
            'skipped_ambiguous': 0,
        }
        updates = []

        for product in Product.objects.all().iterator(chunk_size=5000):
            key = (product.part_no.strip(), product.description.strip())
            if key not in rpt_by_key:
                stats['no_match'] += 1
                continue

            target_id = self._resolve_target_id(product, key, rpt_by_key, ambiguous, legacy_owner, stats)
            if target_id is None:
                continue
            if product.legacy_product_id == target_id:
                stats['already_ok'] += 1
                continue

            owner = legacy_owner.get(target_id)
            if owner is not None and owner != product.id:
                stats['skipped_conflict'] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Skip id={product.id} {product.part_no}: legacy {target_id} owned by id={owner}'
                    )
                )
                continue

            updates.append((product.id, product.legacy_product_id, target_id, product.part_no))
            if product.legacy_product_id in legacy_owner:
                del legacy_owner[product.legacy_product_id]
            legacy_owner[target_id] = product.id

        if not options['dry_run']:
            with transaction.atomic():
                for product_id, old_legacy, new_legacy, part_no in updates:
                    Product.objects.filter(pk=product_id).update(legacy_product_id=new_legacy)
                    stats['updated'] += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Updated id={product_id} {part_no}: {old_legacy} -> {new_legacy}'
                        )
                    )
        else:
            stats['updated'] = len(updates)
            for product_id, old_legacy, new_legacy, part_no in updates:
                self.stdout.write(
                    f'Would update id={product_id} {part_no}: {old_legacy} -> {new_legacy}'
                )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('SYNC SUMMARY'))
        self.stdout.write(f"Already correct: {stats['already_ok']}")
        self.stdout.write(f"Updated: {stats['updated']}")
        self.stdout.write(f"No RPT match (part+desc): {stats['no_match']}")
        self.stdout.write(f"Skipped (legacy ID conflict): {stats['skipped_conflict']}")
        self.stdout.write(f"Skipped (ambiguous RPT key): {stats['skipped_ambiguous']}")

    def _load_rpt(self, rpt_path):
        rpt_by_key = {}
        ambiguous = defaultdict(list)

        with open(rpt_path, 'r', encoding='utf-8', errors='replace') as handle:
            handle.readline()
            handle.readline()
            for line in handle:
                line = line.rstrip('\n\r')
                if not line.strip() or line.lstrip().startswith('('):
                    break
                product_id = int(line[0:11].strip())
                part_no = line[56:76].strip()
                description = line[77:157].strip()
                key = (part_no, description)
                ambiguous[key].append(product_id)
                rpt_by_key[key] = product_id

        return rpt_by_key, ambiguous

    def _resolve_target_id(self, product, key, rpt_by_key, ambiguous, legacy_owner, stats):
        if key not in ambiguous or len(ambiguous[key]) == 1:
            return rpt_by_key[key]

        candidate_ids = ambiguous[key]
        if product.legacy_product_id in candidate_ids:
            return product.legacy_product_id

        for candidate in candidate_ids:
            owner = legacy_owner.get(candidate)
            if owner is None or owner == product.id:
                return candidate

        stats['skipped_ambiguous'] += 1
        self.stdout.write(
            self.style.WARNING(
                f'Skip ambiguous id={product.id} {product.part_no}: candidates {candidate_ids}'
            )
        )
        return None
