from django.test import TestCase
from django.utils import timezone
from .models import Job, JobProductQuote
from crm.models import Customer
from sitework.models import SiteworkQuote, Market
from product.models import ProductQuote


class JobModelTest(TestCase):
    def setUp(self):
        # Create test customer
        self.customer = Customer.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            address="123 Main St",
            city="Anytown",
            state="CA",
            zip="12345"
        )
        
        # Create test market
        self.market = Market.objects.create(
            name="Test Market",
            mcode="TEST",
            status="A"
        )
        
        # Create test sitework quote
        from django.utils import timezone
        self.sitework_quote = SiteworkQuote.objects.create(
            customer=self.customer,
            market=self.market,
            quotedesc="Test Sitework Quote",
            status="A",
            overheadpercent=40.0,
            quotedate=timezone.now().date()
        )
        
        # Create test product quote
        self.product_quote = ProductQuote.objects.create(
            customer=self.customer,
            status="A",
            subtotal=1000.00
        )

    def test_job_creation(self):
        """Test that a job can be created successfully."""
        job = Job.objects.create(
            customer=self.customer,
            job_description="Test job description",
            status="A",
            sitework_quote=self.sitework_quote
        )
        
        self.assertEqual(job.customer, self.customer)
        self.assertEqual(job.job_description, "Test job description")
        self.assertEqual(job.status, "A")
        self.assertEqual(job.sitework_quote, self.sitework_quote)
        self.assertIsNotNone(job.job_code)
        self.assertTrue(job.job_code.startswith("JOB-"))

    def test_job_auto_code_generation(self):
        """Test that job codes are auto-generated correctly."""
        job1 = Job.objects.create(customer=self.customer)
        job2 = Job.objects.create(customer=self.customer)
        
        self.assertNotEqual(job1.job_code, job2.job_code)
        self.assertTrue(job1.job_code.startswith("JOB-"))
        self.assertTrue(job2.job_code.startswith("JOB-"))

    def test_job_product_quote_relationship(self):
        """Test the relationship between jobs and product quotes."""
        job = Job.objects.create(customer=self.customer)
        
        # Create job-product quote relationship
        job_product_quote = JobProductQuote.objects.create(
            job=job,
            product_quote=self.product_quote,
            notes="Test notes"
        )
        
        self.assertEqual(job_product_quote.job, job)
        self.assertEqual(job_product_quote.product_quote, self.product_quote)
        self.assertEqual(job_product_quote.notes, "Test notes")
        
        # Test reverse relationship
        self.assertIn(job_product_quote, job.product_quotes.all())
        self.assertIn(job_product_quote, self.product_quote.jobs.all())

    def test_job_string_representation(self):
        """Test the string representation of job."""
        job = Job.objects.create(
            customer=self.customer,
            job_description="Test job"
        )
        
        expected = f"Job {job.job_code} - {self.customer}"
        self.assertEqual(str(job), expected)
