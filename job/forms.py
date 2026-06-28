from django import forms
from .models import Job, JobType, PurchaseOrder, PurchaseOrderItem, Team, ChangeOrder, Sale, Payment
from crm.models import Customer, StoreLocation, County
from sitework.models import SiteworkQuote
from product.models import ProductQuote, Vendor
from django.contrib.auth.models import User
from accounts.models import UserRole

# US States choices for dropdown
US_STATES = [
    ('', 'Select State'),
    ('AL', 'Alabama'),
    ('AK', 'Alaska'),
    ('AZ', 'Arizona'),
    ('AR', 'Arkansas'),
    ('CA', 'California'),
    ('CO', 'Colorado'),
    ('CT', 'Connecticut'),
    ('DE', 'Delaware'),
    ('FL', 'Florida'),
    ('GA', 'Georgia'),
    ('HI', 'Hawaii'),
    ('ID', 'Idaho'),
    ('IL', 'Illinois'),
    ('IN', 'Indiana'),
    ('IA', 'Iowa'),
    ('KS', 'Kansas'),
    ('KY', 'Kentucky'),
    ('LA', 'Louisiana'),
    ('ME', 'Maine'),
    ('MD', 'Maryland'),
    ('MA', 'Massachusetts'),
    ('MI', 'Michigan'),
    ('MN', 'Minnesota'),
    ('MS', 'Mississippi'),
    ('MO', 'Missouri'),
    ('MT', 'Montana'),
    ('NE', 'Nebraska'),
    ('NV', 'Nevada'),
    ('NH', 'New Hampshire'),
    ('NJ', 'New Jersey'),
    ('NM', 'New Mexico'),
    ('NY', 'New York'),
    ('NC', 'North Carolina'),
    ('ND', 'North Dakota'),
    ('OH', 'Ohio'),
    ('OK', 'Oklahoma'),
    ('OR', 'Oregon'),
    ('PA', 'Pennsylvania'),
    ('RI', 'Rhode Island'),
    ('SC', 'South Carolina'),
    ('SD', 'South Dakota'),
    ('TN', 'Tennessee'),
    ('TX', 'Texas'),
    ('UT', 'Utah'),
    ('VT', 'Vermont'),
    ('VA', 'Virginia'),
    ('WA', 'Washington'),
    ('WV', 'West Virginia'),
    ('WI', 'Wisconsin'),
    ('WY', 'Wyoming'),
    ('DC', 'District of Columbia'),
]


class JobForm(forms.ModelForm):
    """Form for creating and editing Job objects."""
    
    # Override state field to use ChoiceField with dropdown
    state = forms.ChoiceField(
        choices=US_STATES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'position: relative; z-index: 1000;'})
    )
    
    class Meta:
        model = Job
        fields = [
            'customer', 
            'jobtype',
            'job_description', 
            'active',
            'sold',
            'soldby',
            'coordinator',
            'carpenter',
            'storelocation',
            'address',
            'city',
            'state',
            'zip',
            'county',
            'datesold',
            'startdate',
            'completDate',
            'initalcontactdate',
            'initialmeasuredate',
            'present1',
            'present2',
            'present3',
            'actualstart',
            'actualend',
            'saleamount',
            'estdays',
            'terms',
            'cabneededdate',
            'topinstalldate',
            # note: sitework_quote is intentionally excluded from the form to avoid accidental unlinking
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'jobtype': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'job_description': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 3,
                'placeholder': 'Brief description of the job...'
            }),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sold': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'soldby': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'coordinator': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'carpenter': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'storelocation': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'address': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'city': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'zip': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'county': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'datesold': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'startdate': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'completDate': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'initalcontactdate': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'initialmeasuredate': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'present1': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'present2': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'present3': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'actualstart': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'actualend': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'saleamount': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'estdays': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'terms': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'cabneededdate': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
            'topinstalldate': forms.DateTimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make all fields optional except customer
        for field_name, field in self.fields.items():
            if field_name != 'customer':
                field.required = False

        self.fields['customer'].error_messages = {
            'required': 'Please select a customer.',
        }
        self.fields['county'].required = True
        self.fields['county'].error_messages = {
            'required': 'Please select a county.',
        }

        if self.errors:
            for name in self.errors:
                if name in self.fields:
                    css = self.fields[name].widget.attrs.get('class', '')
                    if 'is-invalid' not in css:
                        self.fields[name].widget.attrs['class'] = f'{css} is-invalid'.strip()
        
        # Set querysets for foreign key fields filtered by roles
        # Designer (soldby): filter by role type 'DES'
        designer_users = User.objects.filter(
            is_active=True,
            user_roles__role__type='DES',
            user_roles__is_active=True
        ).distinct().order_by('first_name', 'last_name')
        self.fields['soldby'].queryset = designer_users
        
        # Coordinator: filter by role type 'COR'
        coordinator_users = User.objects.filter(
            is_active=True,
            user_roles__role__type='COR',
            user_roles__is_active=True
        ).distinct().order_by('first_name', 'last_name')
        self.fields['coordinator'].queryset = coordinator_users
        
        # Customize user field labels to show first_name + last_name
        def format_user_label(user):
            """Format user label as first_name + last_name"""
            if user.first_name or user.last_name:
                return f"{user.first_name or ''} {user.last_name or ''}".strip()
            return str(user.username)
        
        # Override label_from_instance for user fields
        self.fields['soldby'].label_from_instance = format_user_label
        self.fields['coordinator'].label_from_instance = format_user_label
        if 'carpenter' in self.fields:
            carpenter_users = User.objects.filter(
                is_active=True,
                user_roles__role__type__in=['CAR', 'CARP2'],
                user_roles__is_active=True
            ).distinct().order_by('first_name', 'last_name')
            self.fields['carpenter'].queryset = carpenter_users
            self.fields['carpenter'].label_from_instance = format_user_label
        
        # Ensure the required job types exist and are active, then filter to only show specific job types
        required_job_types = ['Handyman Job', 'Warranty', 'Remodel']
        for job_type_name in required_job_types:
            job_type, created = JobType.objects.get_or_create(
                name=job_type_name,
                defaults={'status': 'A'}
            )
            # If it exists but is inactive, activate it
            if not created and job_type.status != 'A':
                job_type.status = 'A'
                job_type.save()
        
        # Filter to only show specific job types: Handyman Job, Warranty, Remodel
        self.fields['jobtype'].queryset = JobType.objects.filter(
            status='A',
            name__in=required_job_types
        ).order_by('name')
        self.fields['customer'].queryset = Customer.objects.all().order_by('last_name', 'first_name')
        self.fields['storelocation'].queryset = StoreLocation.objects.all().order_by('name')
        self.fields['county'].queryset = County.objects.all().order_by('name')
        
        # State field is already defined as ChoiceField above with US_STATES
        # Ensure it's properly initialized
        if 'state' in self.initial or (self.instance and self.instance.pk and self.instance.state):
            state_value = self.initial.get('state') or (self.instance.state if self.instance.pk else None)
            if state_value:
                self.fields['state'].initial = state_value
        else:
            self.fields['state'].initial = 'WI'
        
        # Do not expose sitework_quote on the job edit form to prevent accidental clearing
    
    def clean_customer(self):
        customer = self.cleaned_data.get('customer')
        if not customer:
            raise forms.ValidationError('Please select a customer.')
        return customer

    def clean_county(self):
        county = self.cleaned_data.get('county')
        if not county:
            raise forms.ValidationError('Please select a county.')
        return county

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


class JobCreateForm(JobForm):
    """Job create/edit form without lead carpenter (assigned on job detail)."""

    class Meta(JobForm.Meta):
        fields = [f for f in JobForm.Meta.fields if f != 'carpenter']


class JobProductQuoteForm(forms.ModelForm):
    """Form for adding ProductQuotes to Jobs."""
    
    class Meta:
        model = ProductQuote
        fields = ['name', 'status', 'comments']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Product quote name...'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notes about this product quote...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.job = kwargs.pop('job', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.job:
            instance.job = self.job
        if commit:
            instance.save()
        return instance


class JobSearchForm(forms.Form):
    """Form for searching jobs."""
    
    job_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Job code...'
        })
    )
    
    customer_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Customer name...'
        })
    )
    
    invoice_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Invoice Number...'
        })
    )
    
    po_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'PO Number...'
        })
    )
    
    active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    sold = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class JobProductQuoteCreateForm(forms.ModelForm):
    """Form for creating a new ProductQuote for a specific job."""
    
    class Meta:
        model = ProductQuote
        fields = ['name', 'status', 'comments']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter quote name (optional)'
            }),
            'status': forms.Select(
                choices=[('A', 'Active'), ('I', 'Inactive')],
                attrs={'class': 'form-select'}
            ),
            'comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter any comments about this quote...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.job = kwargs.pop('job', None)
        super().__init__(*args, **kwargs)
        
        if self.job:
            # Pre-fill the name with job information
            if not self.instance.pk and not self.data.get('name'):
                self.fields['name'].initial = f"{self.job.job_code} - Product Quote"
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set the customer and job from the job
        if self.job:
            instance.customer = self.job.customer
            instance.job = self.job
        
        # Generate default name if not provided
        if not instance.name and self.job:
            instance.name = f"{self.job.job_code} - Product Quote"
        elif not instance.name:
            instance.name = f"Quote #{instance.id}" if instance.id else "New Quote"
        
        if commit:
            instance.save()
        
        return instance


class VendorForm(forms.ModelForm):
    """Form for creating and editing Vendor objects."""
    
    class Meta:
        model = Vendor
        fields = ['vendor_name', 'contact_name', 'contact_email', 'contact_phone', 'address1', 'address2', 'city', 'state', 'zip', 'comments', 'status']
        widgets = {
            'vendor_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'address1': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'address2': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'city': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'state': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'zip': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'comments': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields optional except vendor_name
        for field_name, field in self.fields.items():
            if field_name != 'vendor_name':
                field.required = False


class PurchaseOrderForm(forms.ModelForm):
    """Form for creating and editing PurchaseOrder objects."""
    
    class Meta:
        model = PurchaseOrder
        fields = ['vendor', 'location', 'arrive_by_date', 'status', 'notes']
        widgets = {
            'vendor': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'location': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'arrive_by_date': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.job = kwargs.pop('job', None)
        super().__init__(*args, **kwargs)
        
        # Set querysets
        self.fields['vendor'].queryset = Vendor.objects.filter(status=True).order_by('vendor_name')
        from job.models import Store
        self.fields['location'].queryset = Store.objects.filter(status='A').order_by('store_name')
        
        # Make all fields required except notes
        for field_name, field in self.fields.items():
            if field_name != 'notes':
                field.required = True
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.job:
            instance.job = self.job
        if commit:
            instance.save()
        return instance


class PurchaseOrderItemForm(forms.ModelForm):
    """Form for creating and editing PurchaseOrderItem objects."""
    
    class Meta:
        model = PurchaseOrderItem
        fields = ['part_number', 'description', 'ordered_date', 'quantity', 'confirmed', 'received', 'received_quantity', 
                 'sent_to_job_quantity', 'parts_storage_location', 'cost', 'note']
        widgets = {
            'part_number': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'ordered_date': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '1'}),
            'confirmed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'received': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'received_quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0'}),
            'sent_to_job_quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0'}),
            'parts_storage_location': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0'}),
            'note': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        self.purchase_order = kwargs.pop('purchase_order', None)
        super().__init__(*args, **kwargs)
        
        # Set queryset for store location field
        from crm.models import StoreLocation
        self.fields['parts_storage_location'].queryset = StoreLocation.objects.all().order_by('name')
        
        # Make required fields
        self.fields['part_number'].required = True
        self.fields['ordered_date'].required = True
        self.fields['quantity'].required = True
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.purchase_order:
            instance.purchase_order = self.purchase_order
        
        # If received is checked, automatically set received_quantity to quantity
        if instance.received and instance.quantity:
            instance.received_quantity = instance.quantity
        
        if commit:
            instance.save()
        return instance


class PurchaseOrderItemInlineFormSet(forms.BaseInlineFormSet):
    """FormSet for inline PurchaseOrderItem editing."""
    
    def clean(self):
        """Validate the formset."""
        if any(self.errors):
            return
        
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                # Validate that received quantity doesn't exceed ordered quantity
                received_qty = form.cleaned_data.get('received_quantity', 0)
                ordered_qty = form.cleaned_data.get('quantity', 0)
                
                if received_qty > ordered_qty:
                    raise forms.ValidationError(
                        f"Received quantity ({received_qty}) cannot exceed ordered quantity ({ordered_qty})"
                    )
                
                # Validate that sent to job quantity doesn't exceed received quantity
                sent_qty = form.cleaned_data.get('sent_to_job_quantity', 0)
                if sent_qty > received_qty:
                    raise forms.ValidationError(
                        f"Sent to job quantity ({sent_qty}) cannot exceed received quantity ({received_qty})"
                    ) 


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'status', 'order_by', 'team_type', 'max_daily_limit', 'average_daily_limit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(choices=[('A', 'Active'), ('I', 'Inactive')], attrs={'class': 'form-select'}),
            'order_by': forms.NumberInput(attrs={'class': 'form-control'}),
            'team_type': forms.Select(choices=[('Remodel', 'Remodel'), ('Tops', 'Tops'), ('Delivery', 'Delivery'), ('Other', 'Other')], attrs={'class': 'form-select'}),
            'max_daily_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'average_daily_limit': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ChangeOrderForm(forms.ModelForm):
    """Form for creating and editing change orders"""
    
    class Meta:
        model = ChangeOrder
        fields = ['product_code', 'description', 'amount', 'order_date', 'tax', 'notes']
        widgets = {
            'product_code': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of the change order'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Amount (can be negative)'
            }),
            'order_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tax': forms.Select(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes (optional)'
            }),
        }
        labels = {
            'product_code': 'Product Code',
            'description': 'Description',
            'amount': 'Amount ($)',
            'order_date': 'Order Date',
            'tax': 'Tax',
            'notes': 'Additional Notes',
        }
        help_texts = {
            'amount': 'Enter a positive value for additions or negative value for deductions. Leave blank for non-monetary change orders.',
            'tax': 'Optional - leave blank for non-monetary change orders.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default order_date to today if creating new change order
        if not self.instance.pk:  # Only for new change orders, not editing
            from datetime import date
            self.fields['order_date'].initial = date.today()
        # Make tax field optional with empty choice
        self.fields['tax'].required = False
        self.fields['tax'].widget.attrs['placeholder'] = 'Select tax (optional)'
        # Make amount field optional
        self.fields['amount'].required = False


class SaleForm(forms.ModelForm):
    """Form for creating and editing sales"""
    
    class Meta:
        model = Sale
        fields = [
            'product_code',
            'cost_amount',
            'tax_amount',
            'sale_amount',
            'sale_date',
            'tax',
            'comment',
            'notes',
        ]
        widgets = {
            'product_code': forms.Select(attrs={
                'class': 'form-control'
            }),
            'cost_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Cost',
            }),
            'tax_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Sales tax ($)',
            }),
            'sale_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Sale amount'
            }),
            'sale_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tax': forms.Select(attrs={
                'class': 'form-control'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Description or comment (optional)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes (optional)'
            }),
        }
        labels = {
            'product_code': 'Product Code',
            'cost_amount': 'Cost ($)',
            'tax_amount': 'Sales tax ($)',
            'sale_amount': 'Sale Amount ($)',
            'sale_date': 'Sale Date',
            'tax': 'Tax code',
            'comment': 'Description/Comment',
            'notes': 'Additional Notes',
        }
        help_texts = {
            'sale_amount': 'Total sale amount for this transaction',
            'tax_amount': 'Dollar amount of sales tax for this line (optional)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter product codes to only show allowed codes
        from product.models import ProductCode
        allowed_codes = ['CK', 'PSD', 'FL', 'CR', 'LV', 'PFX', 'WP', 'MX', 'AP', 'SL', 'SLW', 'CTS', 'SS', 'PFF', 'DEL', 'DS', 'BA', 'HD', 'DIS', 'CTQ']
        self.fields['product_code'].queryset = ProductCode.objects.filter(code__in=allowed_codes).order_by('code')
        # Set default sale_date to today if creating new sale
        if not self.instance.pk:  # Only for new sales, not editing
            from datetime import date
            self.fields['sale_date'].initial = date.today()


class PaymentForm(forms.ModelForm):
    """Form for creating and editing payments"""
    
    class Meta:
        model = Payment
        fields = ['date', 'account_category', 'discount', 'comment', 'amount']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'account_category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Discount amount'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Comment or description (optional)'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Payment amount'
            }),
        }
        labels = {
            'date': 'Date',
            'account_category': 'Account Category',
            'discount': 'Discount ($)',
            'comment': 'Comment',
            'amount': 'Amount ($)',
        }
        help_texts = {
            'amount': 'Payment amount',
            'discount': 'Discount amount (optional)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date to today if creating new payment
        if not self.instance.pk:  # Only for new payments, not editing
            from datetime import date
            self.fields['date'].initial = date.today()
        
        # Filter account categories to only show active ones
        from .models import AccountCategory
        self.fields['account_category'].queryset = AccountCategory.objects.filter(status='A').order_by('code')
        
        # Make discount and comment optional
        self.fields['discount'].required = False
        self.fields['comment'].required = False
