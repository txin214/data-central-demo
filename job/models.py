from django.db import models
from crm.models import Customer,County,StoreLocation
from sitework.models import SiteworkQuote
from product.models import Vendor
from django.contrib.auth.models import User
from django.utils import timezone


class Holiday(models.Model):
    """Holiday model to track non-working days."""
    date = models.DateField(unique=True, help_text="Date of the holiday")
    name = models.CharField(max_length=200, help_text="Name of the holiday")
    recurring = models.BooleanField(default=False, help_text="If True, this holiday repeats every year (e.g., Christmas)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['date']
        verbose_name = 'Holiday'
        verbose_name_plural = 'Holidays'
    
    def __str__(self):
        return f"{self.date} - {self.name}"
    
    @classmethod
    def is_holiday(cls, date):
        """Check if a given date is a holiday."""
        # Only check for these specific US holidays:
        # New Year's Day, Christmas, Thanksgiving, Labor Day, Independence Day, Memorial Day
        try:
            import holidays
            us_holidays = holidays.UnitedStates()
            # Get the holiday name for this date (if any)
            holiday_name = us_holidays.get(date)
            if holiday_name:
                # Only consider these specific holidays
                allowed_holidays = [
                    "New Year's Day",
                    "Christmas",
                    "Thanksgiving",
                    "Labor Day",
                    "Independence Day",
                    "Memorial Day"
                ]
                # Check if the holiday name contains any of our allowed holidays
                if any(allowed in holiday_name for allowed in allowed_holidays):
                    return True
        except ImportError:
            # If holidays library is not installed, fall back to database only
            pass
        
        # Check for custom holidays in database (exact date match)
        if cls.objects.filter(date=date).exists():
            return True
        # Check for recurring custom holidays (same month and day, any year)
        if cls.objects.filter(recurring=True, date__month=date.month, date__day=date.day).exists():
            return True
        return False


class Team(models.Model):
    """Team used for Top Entry scheduling and grouping."""
    STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )
    TYPE_CHOICES = (
        ('Remodel', 'Remodel'),
        ('Tops', 'Tops'),
        ('Delivery', 'Delivery'),
        ('Other', 'Other'),
    )

    name = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='A')
    order_by = models.IntegerField(default=0)
    team_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    max_daily_limit = models.IntegerField(default=0)
    average_daily_limit = models.IntegerField(default=0)

    class Meta:
        ordering = ['order_by', 'name']

    def __str__(self):
        return self.name


class JobTop(models.Model):
    """A single top entry for a job (e.g., Kitchen Quartz Top)."""
    ROOM_CHOICES = [
        ('Kitchen', 'Kitchen'),
        ('Master Bath', 'Master Bath'),
        ('Main Bath', 'Main Bath'),
        ('Powder Room Bath', 'Powder Room Bath'),
        ('Laundry', 'Laundry'),
        ('Other', 'Other'),
        ('Cabinet Mod', 'Cabinet Mod'),
        ('Trim Prep', 'Trim Prep'),
        ('Baseent Bath', 'Baseent Bath'),
        ('Guest Bath', 'Guest Bath'),
        ("Boy's Bath", "Boy's Bath"),
        ("Girl's Bath", "Girl's Bath"),
        ('Work Order', 'Work Order'),
        ('Bar', 'Bar'),
    ]
    TYPE_CHOICES = [
        ('Solid Surface', 'Solid Surface'),
        ('Laminate', 'Laminate'),
        ('Quartz Tops', 'Quartz Tops'),
        ('Stone Tops', 'Stone Tops'),
        ('woodworking', 'woodworking'),
        ('Silestone', 'Silestone'),
        ('Tub Surround', 'Tub Surround'),
        ('Shower Door', 'Shower Door'),
        ('LED LIGHTS', 'LED LIGHTS'),
    ]

    job = models.ForeignKey('job.Job', on_delete=models.CASCADE, related_name='top_entries')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='top_entries')
    room = models.CharField(max_length=40, choices=ROOM_CHOICES)
    top_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    notes = models.CharField(max_length=255, blank=True)
    fab_count = models.PositiveIntegerField(default=0)
    install_count = models.PositiveIntegerField(default=0)
    done = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)

    # Dates (canonical 3)
    template_date = models.DateField(null=True, blank=True)
    fabrication_date = models.DateField(null=True, blank=True)
    install_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.job} - {self.room} - {self.top_type}"


class TopScheduleSlot(models.Model):
    """Calendar slot generated from a JobTop phase/date or standalone events (remodel/delivery)."""
    PHASE_CHOICES = (
        ('template', 'Template'),
        ('fabrication', 'Fabrication'),
        ('install', 'Install'),
        ('extra', 'Extra'),
    )
    EVENT_TYPE_CHOICES = (
        ('top', 'Top'),
        ('remodel', 'Remodel'),
        ('delivery', 'Delivery'),
    )
    job = models.ForeignKey('job.Job', on_delete=models.CASCADE, related_name='top_schedule_slots')
    job_top = models.ForeignKey(JobTop, on_delete=models.CASCADE, null=True, blank=True, related_name='schedule_slots', help_text="Null for standalone events (remodel/delivery)")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='schedule_slots')
    start_date = models.DateField(help_text="Start date of the slot")
    end_date = models.DateField(null=True, blank=True, help_text="End date of the slot (for date ranges)")
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='top', help_text="Type of event: Top (from JobTop), Remodel, or Delivery")
    label = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=40, blank=True, help_text="Word shown inside [] in the calendar")
    confirmed = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['team__order_by', 'start_date', 'position', 'id']
        # Note: Removed unique_together for (job_top, phase) since job_top can be NULL for standalone events
        # Top entry slots should still maintain uniqueness in application logic
        indexes = [
            models.Index(fields=['team', 'start_date']),
            models.Index(fields=['start_date']),
            models.Index(fields=['job_top']),
            models.Index(fields=['job']),
            models.Index(fields=['event_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['job_top', 'phase'],
                condition=models.Q(job_top__isnull=False),
                name='unique_job_top_phase'
            ),
        ]

    def __str__(self):
        return f"{self.start_date} {self.team} {self.phase}"

class JobType(models.Model):
    #id
    name = models.CharField(max_length=50,blank=False)
    status = models.CharField(max_length=1,blank=True)
    
    def __str__(self):
        return f"{self.name}"   
        
class Job(models.Model):
    """Job model that links customers with sitework quotes and product quotes."""
    
    # jobcode suffix codes
    JOB_SUFFIX_CHOICES = [
        ('B1', 'B1'),
        ('B2', 'B2'),
        ('B3', 'B3'),
        ('B4', 'B4'),
        ('KI', 'KI'),    
        ('LN', 'LN'),    
        ('MR', 'MR'),    
        ('LL', 'LL'),    
        ('FL', 'FL'),    
        ('TP', 'TP'),    
        ('DR', 'DR'),    
        ('OT', 'OT'),    
    ]
    
    # Basic job information
    job_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    job_description = models.TextField(blank=True, null=True)
    job_suffix = models.CharField(max_length=3, choices=JOB_SUFFIX_CHOICES, blank=True, null=True)
    
    # New fields from provided code
    sold = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    
    # Relationships
    jobtype = models.ForeignKey(JobType, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='jobs',
        verbose_name='Customer'
    )
    storelocation = models.ForeignKey(StoreLocation, on_delete=models.CASCADE, null=True, blank=True)
    
    # User relationships
    soldby = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    coordinator = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    carpenter = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    
    # Sitework quotes now relate from SiteworkQuote -> Job (see sitework app)
    
    # Date fields
    datesold = models.DateTimeField(null=True, blank=True)
    startdate = models.DateTimeField(null=True, blank=True)
    completDate = models.DateTimeField(null=True, blank=True)
    
    # Address fields
    address = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip = models.CharField(max_length=15, blank=True)
    county = models.ForeignKey(County, on_delete=models.CASCADE)
    township = models.CharField(max_length=100, blank=True)
    
    # Contact and measurement dates
    initalcontactdate = models.DateTimeField(null=True, blank=True)
    initialmeasuredate = models.DateTimeField(null=True, blank=True)
    actualstart = models.DateTimeField(null=True, blank=True)
    actualend = models.DateTimeField(null=True, blank=True)
    
    # Financial and estimation fields
    saleamount = models.DecimalField(max_digits=19, decimal_places=2, null=True, blank=True)
    estdays = models.IntegerField(null=True, blank=True)
    
    # Terms field for payment terms
    TERMS_CHOICES = [
        ('', 'Select Terms'),
        ('NET_RECEIPT', 'Net Due On Receipt'),
        ('NET_15', 'Net 15 Days'),
        ('NET_30', 'Net 30 Days'),
    ]
    terms = models.CharField(max_length=20, choices=TERMS_CHOICES, blank=True, null=True)
    
    # Installation dates
    cabneededdate = models.DateTimeField(null=True, blank=True)
    topinstalldate = models.DateTimeField(null=True, blank=True)
    promised = models.DateTimeField(null=True, blank=True)
    estinstall = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-id']
        verbose_name = 'Job'
        verbose_name_plural = 'Jobs'
    
    def __str__(self):
        return f"Job {self.job_code or self.id} - {self.customer}"
    
    def save(self, *args, **kwargs):
        # Auto-generate job code if not provided
        if not self.job_code:
            # Ensure customer has cust_code generated
            if not self.customer.cust_code:
                self.customer.save()  # This will trigger cust_code generation
                self.customer.refresh_from_db()
            
            # Get customer code (should exist now)
            # Job code format: {cust_code}{editable_suffix}
            # cust_code = first 5 letters of lastname + 2 letters from firstname
            # editable_suffix can be appended by user (multiple letters allowed)
            cust_code = self.customer.cust_code if self.customer.cust_code else "XXXXX"
            
            # Start with just the cust_code (user can add suffix in edit mode)
            self.job_code = cust_code
        
        super().save(*args, **kwargs)


class JobNotes(models.Model):
    """Job Notes model for tracking notes, follow-ups, and assignments."""
    
    # Primary key (NoteID)
    id = models.AutoField(primary_key=True)
    
    # Foreign key to Job (JobID)
    job = models.ForeignKey(
        Job, 
        on_delete=models.CASCADE, 
        related_name='notes',
        verbose_name='Job'
    )
    
    # Note date and time
    note_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Note Date'
    )
    
    # Note content
    note = models.TextField(verbose_name='Note')
    
    # Follow-up date (optional)
    follow_up = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Follow Up Date'
    )
    
    # Assigned to user (AssignedToID)
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_notes',
        verbose_name='Assigned To'
    )
    
    # Completion status
    completed = models.BooleanField(
        default=False,
        verbose_name='Completed'
    )
    
    class Meta:
        ordering = ['-note_date']
        verbose_name = 'Job Note'
        verbose_name_plural = 'Job Notes'
    
    def __str__(self):
        job_code = self.job.job_code or f"Job {self.job.id}"
        note_preview = self.note[:50] + "..." if len(self.note) > 50 else self.note
        return f"{job_code} - {note_preview}"


class JobQuoteProductNotes(models.Model):
    """Model for notes on specific products within quotes for specific jobs."""
    
    # Primary key
    id = models.AutoField(primary_key=True)
    
    # Foreign keys
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='quote_product_notes',
        verbose_name='Job'
    )
    quote = models.ForeignKey(
        'product.ProductQuote',
        on_delete=models.CASCADE,
        related_name='product_notes',
        verbose_name='Quote'
    )
    line_item = models.ForeignKey(
        'product.ProductQuoteLine',
        on_delete=models.CASCADE,
        related_name='job_notes',
        verbose_name='Product Line Item'
    )
    
    # Note content
    note = models.TextField(
        verbose_name='Product Note',
        help_text='Note specific to this product in this job and quote'
    )
    
    # Metadata
    created_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created Date'
    )
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_quote_product_notes',
        verbose_name='Created By'
    )
    modified_date = models.DateTimeField(
        auto_now=True,
        verbose_name='Modified Date'
    )
    modified_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_quote_product_notes',
        verbose_name='Modified By'
    )
    
    class Meta:
        ordering = ['-created_date']
        verbose_name = 'Job Quote Product Note'
        verbose_name_plural = 'Job Quote Product Notes'
        unique_together = ['job', 'line_item']  # One note per product per job
    
    def __str__(self):
        job_code = self.job.job_code or f"Job {self.job.id}"
        product_name = self.line_item.product.part_no if self.line_item.product else "Unknown Product"
        note_preview = self.note[:30] + "..." if len(self.note) > 30 else self.note
        return f"{job_code} - {product_name} - {note_preview}"


class SiteworkLineProgress(models.Model):
    """Progress for sitework quote lines, kept in job app to avoid changing sitework models."""
    line = models.OneToOneField('sitework.SiteworkQuoteLine', on_delete=models.CASCADE, related_name='job_progress')
    progress_percent = models.IntegerField(default=0)
    note = models.TextField(null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'job_sitework_line_progress'

    def __str__(self):
        return f"Line {self.line_id} progress {self.progress_percent}%"


class JobAttachment(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='job_attachments/%Y/%m/%d/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    uploaded_at = models.DateTimeField(default=timezone.now)
    title = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        name = self.title or (self.file.name.split('/')[-1] if self.file else 'Attachment')
        return f"{self.job} - {name}"


class CategoryProductCodeMap(models.Model):
    """
    Maps catalog ProductCategory to ProductCode for generating Sale rows from the primary quote.
    Does not alter product.ProductCategory — this table holds the mapping only.
    """

    product_category = models.OneToOneField(
        "product.ProductCategory",
        on_delete=models.CASCADE,
        related_name="sales_code_map",
    )
    product_code = models.ForeignKey(
        "product.ProductCode",
        on_delete=models.PROTECT,
        related_name="job_category_maps",
    )

    class Meta:
        verbose_name = "Category → sale product code"
        verbose_name_plural = "Category → sale product code maps"

    def __str__(self):
        return f"{self.product_category.product_category} → {self.product_code.code}"


class SubCategory1ProductCodeMap(models.Model):
    """
    Optional finer map: ProductSubCategory1 → ProductCode.
    Used when all quote lines in a category group share the same subcategory1.
    """

    product_sub_category1 = models.OneToOneField(
        "product.ProductSubCategory1",
        on_delete=models.CASCADE,
        related_name="sales_code_map",
    )
    product_code = models.ForeignKey(
        "product.ProductCode",
        on_delete=models.PROTECT,
        related_name="job_subcat1_maps",
    )

    class Meta:
        verbose_name = "Subcategory1 → sale product code"
        verbose_name_plural = "Subcategory1 → sale product code maps"

    def __str__(self):
        return f"{self.product_sub_category1.product_sub_category} → {self.product_code.code}"


class Sale(models.Model):
    """Represents a sold job with payment tracking - a job can have multiple sales"""
    TAX_CHOICES = [
        ('EX', 'EX'),
        ('ST', 'ST'),
        ('UT', 'UT'),
        ('LB', 'LB'),
        ('SU', 'SU'),
    ]
    
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='sales')
    source_quote = models.ForeignKey(
        'product.ProductQuote',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_sales',
        help_text='If set, this row was generated from this product quote (regenerate replaces rows tied to the same quote).',
    )
    product_code = models.ForeignKey('product.ProductCode', on_delete=models.SET_NULL, null=True, blank=True, help_text="Product code category")
    cost_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total cost basis for this sale line (e.g. sum of unit costs × qty)",
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Sales tax in dollars (when tracked separately from sale amount)",
    )
    sale_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total sale amount for this sale")
    sale_date = models.DateField(null=True, blank=True, help_text="Date when the job was sold (defaults to creation date)")
    tax = models.CharField(max_length=2, choices=TAX_CHOICES, default='UT', help_text="Tax status")
    comment = models.TextField(blank=True, help_text="Description or comment for this sale")
    notes = models.TextField(blank=True, help_text="Additional notes about the sale or payments")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='sales_created', help_text="User who created this sale")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-sale_date']
    
    def __str__(self):
        return f"Sale: {self.job.job_code} - ${self.sale_amount} ({self.sale_date})"
    
    @property
    def job_code(self):
        """Get the job code from the related job"""
        return self.job.job_code
    
    @property
    def sales_person(self):
        """Get the sales person (soldby) from the related job"""
        return self.job.soldby
    
    @property
    def sales_person_name(self):
        """Get the sales person name"""
        return f"{self.sales_person.first_name} {self.sales_person.last_name}" if self.sales_person else "N/A"
    
    @property
    def total_contract_amount(self):
        """Get the total sale amount - now independent from job.saleamount"""
        return self.sale_amount


class ChangeOrder(models.Model):
    """Track change orders that modify sold job contract amounts"""
    TAX_CHOICES = [
        ('EX', 'EX'),
        ('ST', 'ST'),
        ('UT', 'UT'),
        ('LB', 'LB'),
        ('SU', 'SU'),
    ]
    
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='change_orders', 
                           help_text="Job this change order belongs to (must be sold)")
    product_code = models.ForeignKey('product.ProductCode', on_delete=models.SET_NULL, null=True, blank=True, help_text="Product code category")
    description = models.TextField(help_text="Description of the change")
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                help_text="Amount to add/subtract (can be negative, optional for non-monetary change orders)")
    order_date = models.DateField(help_text="Date of the change order")
    tax = models.CharField(max_length=2, choices=TAX_CHOICES, null=True, blank=True, help_text="Tax status (optional for non-monetary change orders)")
    notes = models.TextField(blank=True, help_text="Additional notes")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name='change_orders_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-order_date', '-created_at']
        verbose_name = 'Change Order'
        verbose_name_plural = 'Change Orders'
    
    def __str__(self):
        if self.amount is not None:
            sign = "+" if self.amount >= 0 else ""
            return f"{self.job.job_code} - {sign}${self.amount}"
        else:
            return f"{self.job.job_code} - {self.description[:30]}"
    
    def save(self, *args, **kwargs):
        """Validate job is sold"""
        # Validate that the job is sold
        if not self.job.sold:
            from django.core.exceptions import ValidationError
            raise ValidationError("Cannot create change order for a job that is not sold")
        
        super().save(*args, **kwargs)
    
    @property
    def is_increase(self):
        """Check if this is an increase (positive amount)"""
        return self.amount is not None and self.amount > 0


class PaymentType(models.Model):
    """Payment type model for categorizing different payment types"""
    STATUS_CHOICES = [
        ('A', 'Active'),
        ('I', 'Inactive'),
    ]
    
    description = models.CharField(max_length=200, help_text="Description of the payment type")
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='A', help_text="Status: A=Active, I=Inactive")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Payment Type'
        verbose_name_plural = 'Payment Types'
    
    def __str__(self):
        return f"{self.id} - {self.description}"


class AccountCategory(models.Model):
    """Account category model for categorizing different account types"""
    STATUS_CHOICES = [
        ('A', 'Active'),
        ('I', 'Inactive'),
    ]
    
    code = models.CharField(max_length=20, unique=True, help_text="Account category code")
    description = models.CharField(max_length=200, help_text="Description of the account category")
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='A', help_text="Status: A=Active, I=Inactive")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = 'Account Category'
        verbose_name_plural = 'Account Categories'
    
    def __str__(self):
        return f"{self.id} - {self.code} - {self.description}"


class Payment(models.Model):
    """Payment model for tracking payments"""
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='payments', help_text="Job this payment belongs to")
    date = models.DateField(help_text="Payment date")
    account_category = models.ForeignKey(AccountCategory, on_delete=models.SET_NULL, null=True, blank=True, help_text="Account category for this payment")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Discount amount")
    comment = models.TextField(blank=True, help_text="Comment or description for this payment")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Payment amount")
    by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments_created', help_text="User who created this payment")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
    
    def __str__(self):
        return f"Payment: {self.job.job_code} - ${self.amount} ({self.date})"
    
    @property
    def is_decrease(self):
        """Check if this is a decrease (negative amount)"""
        return self.amount < 0


class Store(models.Model):
    """Store model for managing store locations."""
    
    STATUS_CHOICES = [
        ('A', 'Active'),
        ('I', 'Inactive'),
    ]
    
    store_name = models.CharField(max_length=100, verbose_name='Store Name')
    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='A',
        verbose_name='Status'
    )
    address1 = models.CharField(max_length=100, blank=True, null=True, verbose_name='Address1')
    address2 = models.CharField(max_length=100, blank=True, null=True, verbose_name='Address2')
    city = models.CharField(max_length=50, blank=True, null=True, verbose_name='City')
    state = models.CharField(max_length=2, blank=True, null=True, verbose_name='State')
    zipcode = models.CharField(max_length=12, blank=True, null=True, verbose_name='Zipcode')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Phone')
    
    class Meta:
        ordering = ['store_name']
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'
    
    def __str__(self):
        return self.store_name


class PurchaseOrder(models.Model):
    """Purchase Order model for managing vendor orders."""
    
    # Basic PO information
    po_number = models.CharField(max_length=50, unique=True, verbose_name='PO Number')
    job = models.ForeignKey(
        Job, 
        on_delete=models.CASCADE, 
        related_name='purchase_orders',
        verbose_name='Job'
    )
    vendor = models.ForeignKey(
        Vendor, 
        on_delete=models.CASCADE, 
        related_name='purchase_orders',
        verbose_name='Vendor'
    )
    
    # Location and shipping
    location = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        verbose_name='Location',
        null=True,
        blank=True  # Temporarily allow blank for migration
    )
    arrive_by_date = models.DateField(verbose_name='Arrive By Date')
    
    # Status and dates
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('sent', 'Sent'),
            ('partial', 'Partially Received'),
            ('received', 'Fully Received'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        verbose_name='Status'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_purchase_orders',
        verbose_name='Created By'
    )
    
    # Notes
    notes = models.TextField(blank=True, null=True, verbose_name='PO Notes')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
    
    def __str__(self):
        return f"PO {self.po_number} - {self.vendor.vendor_name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate PO number if not provided
        if not self.po_number:
            # Get job code
            job_code = self.job.job_code or f"Job{self.job.id}"
            
            # Get first 4 letters of vendor name (uppercase)
            vendor_name = self.vendor.vendor_name or ""
            vendor_prefix = vendor_name[:4].upper() if len(vendor_name) >= 4 else vendor_name.upper().ljust(4, 'X')
            
            # Find the next sequential number for this job+vendor combination
            # Query existing POs with same job and vendor to find the highest number
            existing_pos = PurchaseOrder.objects.filter(
                job=self.job,
                vendor=self.vendor
            ).exclude(po_number='').values_list('po_number', flat=True)
            
            # Extract numbers from existing PO numbers with this pattern
            max_number = 0
            pattern_prefix = f"{job_code}-{vendor_prefix}-"
            for po_num in existing_pos:
                if po_num.startswith(pattern_prefix):
                    try:
                        # Extract the number part after the last dash
                        number_part = po_num.split('-')[-1]
                        number = int(number_part)
                        if number > max_number:
                            max_number = number
                    except (ValueError, IndexError):
                        continue
            
            # Increment for the new PO
            next_number = max_number + 1
            
            # Format: {job_code}-{vendor_prefix}-{number:02d}
            self.po_number = f"{job_code}-{vendor_prefix}-{next_number:02d}"
        
        super().save(*args, **kwargs)


class PurchaseOrderItem(models.Model):
    """Individual items within a purchase order."""
    
    purchase_order = models.ForeignKey(
        PurchaseOrder, 
        on_delete=models.CASCADE, 
        related_name='items',
        verbose_name='Purchase Order'
    )
    
    # Item details
    part_number = models.CharField(max_length=100, verbose_name='Part Number')
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name='Description')
    
    # Ordering information
    ordered_date = models.DateField(verbose_name='Ordered Date')
    quantity = models.PositiveIntegerField(verbose_name='Quantity Ordered')
    confirmed = models.BooleanField(default=False, verbose_name='Confirmed')
    
    # Receiving information
    received = models.BooleanField(default=False, verbose_name='Received')
    received_quantity = models.PositiveIntegerField(default=0, verbose_name='Received Quantity')
    sent_to_job_quantity = models.PositiveIntegerField(default=0, verbose_name='Sent to Job Quantity')
    
    # Storage and cost
    parts_storage_location = models.ForeignKey(
        StoreLocation,
        on_delete=models.SET_NULL,
        blank=True, 
        null=True, 
        related_name='purchase_order_items',
        verbose_name='Parts Storage Location'
    )
    cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        verbose_name='Unit Cost'
    )
    
    # Notes
    note = models.TextField(blank=True, null=True, verbose_name='Item Note')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['ordered_date', 'part_number']
        verbose_name = 'Purchase Order Item'
        verbose_name_plural = 'Purchase Order Items'
    
    def __str__(self):
        return f"{self.part_number} - {self.quantity} units"
    
    @property
    def total_cost(self):
        """Calculate total cost for this item."""
        if self.cost and self.quantity:
            return self.cost * self.quantity
        return 0
    
