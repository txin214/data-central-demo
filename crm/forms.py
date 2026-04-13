from django import forms
from crm.models import Customer
from django.forms import ModelForm

class CustomerForm(ModelForm):
    status_flag = forms.ChoiceField(
        choices=[
            ('', '---------'),
            ('A', 'Active'),
            ('B', 'Builder'),
            ('P', 'Pending'),
            ('I', 'Inactive'),
            ('C', 'Closed'),
        ],
        widget=forms.Select(attrs={'style': 'width: 150px;'}),
        required=False
    )
    
    emailoptout = forms.BooleanField(
        widget=forms.CheckboxInput(),
        required=False,
        label="Email Opt Out"
    )
    
    def clean_cust_code(self):
        """Convert cust_code to uppercase and validate uniqueness"""
        cust_code = self.cleaned_data.get('cust_code')
        
        # Auto-generate customer code if blank
        if not cust_code:
            first_name = self.cleaned_data.get('first_name', '')
            last_name = self.cleaned_data.get('last_name', '')
            
            if first_name and last_name:
                # Get first 5 letters of last name and first 2 letters of first name
                last_part = last_name[:5].upper()
                first_part = first_name[:2].upper()
                cust_code = f"{last_part}{first_part}"
                
                # Ensure uniqueness by adding number if needed
                original_code = cust_code
                counter = 1
                while Customer.objects.filter(cust_code=cust_code).exists():
                    cust_code = f"{original_code}{counter}"
                    counter += 1
            else:
                # If names are not available, leave it blank
                return cust_code
        else:
            cust_code = cust_code.upper()
            
        # Check for uniqueness (exclude current instance for updates)
        queryset = Customer.objects.filter(cust_code=cust_code)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise forms.ValidationError(
                f"Customer Code '{cust_code}' already exists. Please use a different code."
            )
        
        return cust_code
    
    class Meta:
        model = Customer
        fields = "__all__"
        exclude = ['status_flag', 'emailoptout']  # Exclude fields we're defining manually
