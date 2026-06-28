"""Report remaining gaps between Product table and product1.rpt."""
import csv
import os
from collections import defaultdict

from django.core.management.base import BaseCommand

from product.models import Product


class Command(BaseCommand):
    help = 'Compare products in DB against product1.rpt and report what is left.'

    def add_arguments(self, parser):
        parser.add_argument(
            'rpt_file',
            nargs='?',
            default='product1.rpt',
            help='Path to the .rpt file (default: product1.rpt)',
        )
        parser.add_argument(
            '--export-dir',
            default='.',
            help='Directory for CSV exports (default: project root)',
        )

    def handle(self, *args, **options):
        rpt_path = options['rpt_file']
        if not os.path.isabs(rpt_path):
            rpt_path = os.path.join(os.getcwd(), rpt_path)

        export_dir = options['export_dir']
        if not os.path.isabs(export_dir):
            export_dir = os.path.join(os.getcwd(), export_dir)

        rpt_by_id, rpt_by_key = self._load_rpt(rpt_path)
        results = self._analyze(rpt_by_id, rpt_by_key)

        self._print_report(results, rpt_by_id)
        self._export_csvs(results, export_dir)

    def _load_rpt(self, rpt_path):
        rpt_by_id = {}
        rpt_by_key = defaultdict(list)

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
                rpt_by_id[product_id] = {'part_no': part_no, 'description': description}
                rpt_by_key[(part_no, description)].append(product_id)

        return rpt_by_id, rpt_by_key

    def _analyze(self, rpt_by_id, rpt_by_key):
        no_legacy = []
        no_rpt_match = []
        part_desc_differs = []
        legacy_wrong = []
        already_ok = 0

        for product in Product.objects.all().iterator(chunk_size=5000):
            if product.legacy_product_id is None:
                no_legacy.append(product)
                continue

            rpt_row = rpt_by_id.get(product.legacy_product_id)
            if rpt_row:
                if (
                    product.part_no == rpt_row['part_no']
                    and product.description == rpt_row['description']
                ):
                    already_ok += 1
                else:
                    part_desc_differs.append({
                        'db_id': product.id,
                        'part_no': product.part_no,
                        'description': product.description,
                        'legacy_product_id': product.legacy_product_id,
                        'rpt_part_no': rpt_row['part_no'],
                        'rpt_description': rpt_row['description'],
                    })
                continue

            key = (product.part_no.strip(), product.description.strip())
            if key in rpt_by_key:
                target_id = rpt_by_key[key][0]
                if product.legacy_product_id != target_id:
                    legacy_wrong.append({
                        'db_id': product.id,
                        'part_no': product.part_no,
                        'description': product.description,
                        'legacy_product_id': product.legacy_product_id,
                        'rpt_product_id': target_id,
                    })
                else:
                    already_ok += 1
            else:
                no_rpt_match.append({
                    'db_id': product.id,
                    'part_no': product.part_no,
                    'description': product.description,
                    'legacy_product_id': product.legacy_product_id,
                })

        db_legacy_ids = set(
            Product.objects.exclude(legacy_product_id__isnull=True).values_list(
                'legacy_product_id', flat=True
            )
        )
        rpt_not_in_db = sorted(set(rpt_by_id.keys()) - db_legacy_ids)

        return {
            'total_db': Product.objects.count(),
            'with_legacy': Product.objects.exclude(legacy_product_id__isnull=True).count(),
            'already_ok': already_ok,
            'no_legacy': no_legacy,
            'no_rpt_match': no_rpt_match,
            'part_desc_differs': part_desc_differs,
            'legacy_wrong': legacy_wrong,
            'rpt_not_in_db': rpt_not_in_db,
            'rpt_count': len(rpt_by_id),
        }

    def _print_report(self, results, rpt_by_id):
        no_legacy = results['no_legacy']
        no_rpt_match = results['no_rpt_match']
        part_desc_differs = results['part_desc_differs']
        legacy_wrong = results['legacy_wrong']

        self.stdout.write('=== TOTALS ===')
        self.stdout.write(f"DB products: {results['total_db']}")
        self.stdout.write(f"RPT rows: {results['rpt_count']}")
        self.stdout.write(f"DB with legacy_product_id: {results['with_legacy']}")
        self.stdout.write(f"DB without legacy_product_id: {len(no_legacy)}")
        self.stdout.write('')
        self.stdout.write('=== MATCH STATUS ===')
        self.stdout.write(self.style.SUCCESS(f"Fully aligned with RPT: {results['already_ok']}"))
        self.stdout.write(f"Legacy ID ok, part/desc still differs: {len(part_desc_differs)}")
        self.stdout.write(f"Part+desc in RPT, wrong legacy ID: {len(legacy_wrong)}")
        self.stdout.write(f"No RPT match (part+desc or legacy): {len(no_rpt_match)}")
        self.stdout.write(f"No legacy_product_id: {len(no_legacy)}")
        self.stdout.write('')
        self.stdout.write(f"RPT Product_IDs not represented in DB: {len(results['rpt_not_in_db'])}")

        if no_legacy:
            self.stdout.write('')
            self.stdout.write(f'--- No legacy_product_id ({len(no_legacy)}) ---')
            for product in no_legacy:
                self.stdout.write(
                    f"  id={product.id} part={product.part_no!r} desc={product.description[:60]!r}"
                )

        if no_rpt_match:
            self.stdout.write('')
            self.stdout.write(f'--- No RPT match ({len(no_rpt_match)}) ---')
            for row in no_rpt_match:
                self.stdout.write(
                    f"  id={row['db_id']} legacy={row['legacy_product_id']} part={row['part_no']!r}"
                )
                self.stdout.write(f"    desc={row['description'][:70]!r}")

        if part_desc_differs:
            self.stdout.write('')
            self.stdout.write(f'--- Part/desc differs from RPT ({len(part_desc_differs)}) ---')
            for row in part_desc_differs:
                self.stdout.write(
                    f"  id={row['db_id']} legacy={row['legacy_product_id']}"
                )
                self.stdout.write(
                    f"    db part={row['part_no']!r} -> rpt {row['rpt_part_no']!r}"
                )
                self.stdout.write(f"    db desc={row['description'][:60]!r}")
                self.stdout.write(f"    rpt desc={row['rpt_description'][:60]!r}")

        if legacy_wrong:
            self.stdout.write('')
            self.stdout.write(f'--- Wrong legacy ID ({len(legacy_wrong)}) ---')
            for row in legacy_wrong:
                self.stdout.write(
                    f"  id={row['db_id']} legacy={row['legacy_product_id']} "
                    f"should be {row['rpt_product_id']} part={row['part_no']!r}"
                )

        if results['rpt_not_in_db']:
            self.stdout.write('')
            self.stdout.write('--- Sample RPT IDs missing from DB (first 10) ---')
            for product_id in results['rpt_not_in_db'][:10]:
                row = rpt_by_id[product_id]
                self.stdout.write(
                    f"  Product_ID={product_id} part={row['part_no']!r} "
                    f"desc={row['description'][:50]!r}"
                )

    def _export_csvs(self, results, export_dir):
        exports = [
            ('rpt_sync_no_legacy.csv', results['no_legacy'], self._no_legacy_row),
            ('rpt_sync_no_rpt_match.csv', results['no_rpt_match'], None),
            ('rpt_sync_part_desc_differs.csv', results['part_desc_differs'], None),
            ('rpt_sync_wrong_legacy_id.csv', results['legacy_wrong'], None),
            (
                'rpt_sync_rpt_not_in_db.csv',
                [{'product_id': pid} for pid in results['rpt_not_in_db']],
                lambda row: {
                    'product_id': row['product_id'],
                    **results.get('_rpt_by_id', {}).get(row['product_id'], {}),
                },
            ),
        ]

        for filename, rows, row_fn in exports:
            if filename == 'rpt_sync_rpt_not_in_db.csv':
                continue
            path = os.path.join(export_dir, filename)
            if not rows:
                continue
            fieldnames = list(rows[0].keys()) if isinstance(rows[0], dict) else ['db_id', 'part_no', 'description']
            with open(path, 'w', newline='', encoding='utf-8') as handle:
                if isinstance(rows[0], dict):
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                else:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    for product in rows:
                        writer.writerow(row_fn(product))
            self.stdout.write(self.style.SUCCESS(f'Exported {path} ({len(rows)} rows)'))

        rpt_path = os.path.join(export_dir, 'rpt_sync_rpt_not_in_db.csv')
        if results['rpt_not_in_db']:
            with open(rpt_path, 'w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(['product_id'])
                for product_id in results['rpt_not_in_db']:
                    writer.writerow([product_id])
            self.stdout.write(
                self.style.SUCCESS(
                    f'Exported {rpt_path} ({len(results["rpt_not_in_db"])} rows)'
                )
            )

    def _no_legacy_row(self, product):
        return {
            'db_id': product.id,
            'part_no': product.part_no,
            'description': product.description,
        }
