from django import forms
from crm.models import Customer
from sitework.models import SiteworkSubCat, SiteworkQuote,Market
from django.forms import ModelForm
from django.contrib.auth.models import User
from accounts.models import UserRole


class QtyForm(forms.Form):
    qty = forms.IntegerField(label="Qty", min_value=0)

# not used
class SiteworkSubCatForm(ModelForm):
    class Meta:
        model = SiteworkSubCat
        fields = ["workdesc","quantitydesc","basecost","unitamount","allowance","material","labor","profit","subfee"]

##NEW
class SiteworkQuoteForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=[
            ('', '---------'),
            ('A', 'Active'),
            ('P', 'Pending'),
            ('C', 'Completed'),
            ('X', 'Cancelled'),
        ],
        widget=forms.Select(attrs={'style': 'width: 150px;'}),
        required=False
    )
    
    class Meta:
        model = SiteworkQuote
        fields = '__all__'

    labels = {
        'customer' : 'Customer',
        'quotedate' : 'Date',
        'quotedesc' : 'Quote Description',
        'status' : 'Status Flag',
        'kbflag' : 'Kit/Bath Flag',
        'overheadpercent' : 'Overhead %',
        'market' : 'Market',
        }
    widgets ={
        'customer' : forms.ModelChoiceField(queryset=Customer.objects.all()),
        'quotedate' : forms.DateInput(attrs={'placeholder' : 'today', 'type': 'date'}),
        'quotedesc' : forms.TextInput(),
        'kbflag' : forms.Select(),
        'overheadpercent' : forms.NumberInput(),
        'market' : forms.ModelChoiceField(queryset=Market.objects.all()),

    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(f"DEBUG: Available fields: {list(self.fields.keys())}")
        # Set default date to today if no date is provided
        if not self.instance.pk and not self.data:  # Only for new instances
            from datetime import date
            self.fields['quotedate'].initial = date.today()
        
        # Set kbflag to use Select widget and remove empty choice
        if 'kbflag' in self.fields:
            self.fields['kbflag'].widget = forms.Select(attrs={'style': 'width: 150px;'})
            # Remove the empty choice (---------)
            self.fields['kbflag'].choices = [choice for choice in self.fields['kbflag'].choices if choice[0] != '']
        
        # Filter quotedby field to show users with active roles (same as employee list)
        # Exclude users with NONE type roles (No Category) like "bill"
        if 'quotedby' in self.fields:
            # Show users with active roles, excluding NONE type roles
            users_with_roles = User.objects.filter(
                user_roles__is_active=True,
                is_active=True
            ).exclude(
                user_roles__role__type='NONE'
            ).distinct().order_by('first_name', 'last_name')
            self.fields['quotedby'].queryset = users_with_roles
            
            # Customize user field label to show first_name + last_name (same as Job form)
            def format_user_label(user):
                """Format user label as first_name + last_name"""
                if user.first_name or user.last_name:
                    return f"{user.first_name or ''} {user.last_name or ''}".strip()
                return str(user.username)
            
            self.fields['quotedby'].label_from_instance = format_user_label
    #customer = models.ForeignKey(Customer,on_delete=models.CASCADE,null=True)
    #quotedate = models.DateField(blank=True)
    #quotedesc = models.CharField(max_length=250,blank=False)
    #status = models.CharField(max_length=1,blank=True)
    #kbflag = models.CharField(max_length=1,blank=True)
    #overheadpercent = models.FloatField(blank=False)
    #market = models.ForeignKey(Market,on_delete=models.CASCADE,null=True)
    #FUTURE quoteby fk Users
    #FUTURE fk-jobid
