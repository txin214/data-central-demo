"""Apply CostPool-based sell multipliers to all products (one-time / batch refresh)."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import now

from product.models import Product


class Command(BaseCommand):
    help = (
        'Set retail/builder/surplus multiplier fields from CostPool taxonomy for every product. '
        'No pool match → 0.6 / 0.7 / 1. Sell price fields are not modified.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Bulk update chunk size',
        )

    def handle(self, *args, **options):
        batch = max(50, options['batch_size'])

        qs = Product.objects.select_related(
            'manufacturer',
            'category',
            'sub_category1',
            'sub_category2',
            'cost_pool',
        )

        total = qs.count()
        updated = 0
        pending = []

        self.stdout.write(f'Processing {total} products…')

        for p in qs.iterator(chunk_size=batch):
            p.apply_cost_pool_multipliers()
            p.date_updated = now()
            pending.append(p)

            if len(pending) >= batch:
                with transaction.atomic():
                    Product.objects.bulk_update(
                        pending,
                        [
                            'cost_pool',
                            'retail_sell_multiplier',
                            'builder_sell_multiplier',
                            'surplus_sell_multiplier',
                            'date_updated',
                        ],
                    )
                updated += len(pending)
                self.stdout.write(f'  … {updated} / {total}')
                pending.clear()

        if pending:
            with transaction.atomic():
                Product.objects.bulk_update(
                    pending,
                    [
                        'cost_pool',
                        'retail_sell_multiplier',
                        'builder_sell_multiplier',
                        'surplus_sell_multiplier',
                        'date_updated',
                    ],
                )
            updated += len(pending)

        self.stdout.write(self.style.SUCCESS(f'Done. Updated {updated} product rows.'))
