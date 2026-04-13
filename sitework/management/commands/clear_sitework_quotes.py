from django.core.management.base import BaseCommand
from sitework.models import SiteworkQuote, SiteworkQuoteLine


class Command(BaseCommand):
    help = 'Remove all sitework quotes and their associated quote lines from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete all sitework quotes',
        )

    def handle(self, *args, **options):
        quote_count = SiteworkQuote.objects.count()
        line_count = SiteworkQuoteLine.objects.count()
        
        self.stdout.write(f'Found {quote_count} sitework quotes and {line_count} quote lines')
        
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will permanently delete all sitework quotes and quote lines. '
                    'Use --confirm to proceed.'
                )
            )
            return
        
        # Delete quote lines first (due to foreign key constraints)
        deleted_lines = SiteworkQuoteLine.objects.all().delete()
        self.stdout.write(f'Deleted {deleted_lines[0]} quote lines')
        
        # Delete quotes
        deleted_quotes = SiteworkQuote.objects.all().delete()
        self.stdout.write(f'Deleted {deleted_quotes[0]} quotes')
        
        self.stdout.write(
            self.style.SUCCESS('Successfully removed all sitework quotes and quote lines!')
        ) 