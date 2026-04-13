from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory
from .models import Color, Finish, Manufacturer, Product, ProductCategory, ProductQuote, ProductSubCategory1, ProductSubCategory2, ProductAccessory, ProductImage, Vendor, AdHoc, CostPool


class CustomManyToManyField(forms.ModelMultipleChoiceField):
    """Custom ManyToMany field that handles 'none' values and comma-separated strings"""
    
    def clean(self, value):
        if value == 'none' or value == '' or value is None:
            return []
        elif isinstance(value, str) and ',' in value:
            # Handle comma-separated string
            try:
                # Split by comma and convert to integers
                ids = [int(id.strip()) for id in value.split(',') if id.strip()]
                return super().clean(ids)
            except (ValueError, TypeError):
                return []
        return super().clean(value)


class ProductForm(forms.ModelForm):
    accessories_search = forms.CharField(required=False, label="Search Accessories",
                                         widget=forms.TextInput(attrs={'placeholder': 'Search for accessories...'}))
    images = forms.FileField(required=False, label="Product Images",
                             widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))
    primary_image = forms.ChoiceField(required=False, label="Set Primary Image",
                                      widget=forms.RadioSelect, choices=[])

    class Meta:
        model = Product
        fields = ['category', 'sub_category1', 'sub_category2', 'manufacturer', 'part_no', 'description', 
                  'pref_vendor', 'alt_vendor', 'width', 'height', 'depth', 'drill', 'min_order', 
                  'min_stock', 'unit_material_cost', 'unit_lead_time', 'unit_labor_minutes', 'unit_labor_cost', 
                  'unit_total_cost', 'bulk_material_cost', 'bulk_qty', 'bulk_lead_time', 'bulk_labor_cost', 
                  'bulk_total_cost', 'retail_sell', 'builder_sell', 'surplus_sell', 'upc', 'product_lbl',
                  'status', 'component_level', 'product_type', 'unit_base_cost', 'date_entered','date_updated',
                  'unit_top_install_minutes', 'accessories', 'components','retail_sell_multiplier', 
                  'builder_sell_multiplier', 'surplus_sell_multiplier','website']
        widgets = {
            'date_entered': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'date_updated': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_field_attributes()
        self.fields['status'].choices = [(True, 'A'), (False, 'I')]
        
        # Make date fields not required to prevent validation issues
        self.fields['date_entered'].required = False
        self.fields['date_updated'].required = False
        
        # Make component_level not required since it has a default value
        self.fields['component_level'].required = False
        
        # Set alphabetical ordering for dropdown fields
        self.fields['category'].queryset = ProductCategory.objects.filter(status=True).order_by('product_category')
        self.fields['manufacturer'].queryset = Manufacturer.objects.filter(status=True).order_by('manufacturer_name')
        self.fields['pref_vendor'].queryset = Vendor.objects.filter(status=True).order_by('vendor_name')
        self.fields['alt_vendor'].queryset = Vendor.objects.filter(status=True).order_by('vendor_name')
        
        # Override ManyToMany fields with custom field classes
        self.fields['accessories'] = CustomManyToManyField(
            queryset=Product.objects.all(),
            required=False,
            widget=forms.HiddenInput(),
            initial=[]
        )
        self.fields['components'] = CustomManyToManyField(
            queryset=Product.objects.all(),
            required=False,
            widget=forms.HiddenInput(),
            initial=[]
        )
        
        if not self.instance.pk:
            self.fields['status'].initial = True
            # Set default values for new products
            self.fields['surplus_sell_multiplier'].initial = 1
            self.fields['component_level'].initial = 1
            self.fields['product_type'].initial = 'product'
        if self.instance.pk:
            self.fields['primary_image'].choices = [(img.id, img.image.name) for img in self.instance.images.all()]
            # Ensure date fields are properly populated for existing products
            if self.instance.date_entered:
                # Format datetime for HTML5 datetime-local input (YYYY-MM-DDTHH:MM)
                self.fields['date_entered'].initial = self.instance.date_entered.strftime('%Y-%m-%dT%H:%M')
            # Don't set initial for date_updated as it should be auto-updated
            # Ensure component_level and product_type are properly set for existing products
            if self.instance.component_level:
                self.fields['component_level'].initial = self.instance.component_level
            if self.instance.product_type:
                self.fields['product_type'].initial = self.instance.product_type

    def _set_field_attributes(self):
        field_attrs = {
            'manufacturer': {'id': "id_manufacturer", 'style': 'width: 300px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'category': {'id': "id_category", 'style': 'width: 300px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'sub_category1': {'id': "id_sub_category1", 'style': 'width: 300px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'sub_category2': {'id': "id_sub_category2", 'style': 'width: 300px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'unit_lead_time': {'id': 'id_unit_lead_time', 'style': 'width: 200px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'bulk_lead_time': {'id': 'id_bulk_lead_time', 'style': 'width: 200px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'pref_vendor': {'id': "id_pref_vendor", 'style': 'width: 300px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'alt_vendor': {'id': "id_alt_vendor", 'style': 'width: 300px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'date_entered': {'id': "id_date_entered", 'style': 'width: 250px; height: 30px;'},
            'date_updated': {'id': "id_date_updated", 'style': 'width: 250px; height: 30px;'},
            'component_level': {'id': 'id_component_level', 'style': 'width: 150px; height: 30px;'},
            'product_type': {'id': 'id_product_type', 'style': 'width: 150px; height: 30px;'},
            'status': {'id': 'id_status', 'style': 'width: 50px; height: 20px;'},
            'width': {'id': 'width', 'style': 'width: 80px; height: 25px; min-width: 60px; max-width: 100%;', 'class': 'form-control-responsive'},
            'height': {'id': 'height', 'style': 'width: 80px; height: 25px; min-width: 60px; max-width: 100%;', 'class': 'form-control-responsive'},
            'depth': {'id': 'depth', 'style': 'width: 80px; height: 25px; min-width: 60px; max-width: 100%;', 'class': 'form-control-responsive'},
            'part_no': {'id': 'partNumber1', 'style': 'width: 400px; height: 30px; min-width: 250px; max-width: 100%;', 'class': 'form-control-responsive'},
            'website': {'id': 'website', 'style': 'width: 400px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'upc': {'id': 'upcField', 'style': 'width: 400px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'product_lbl': {'id': 'productLblField', 'style': 'width: 400px; height: 30px; min-width: 200px; max-width: 100%;', 'class': 'form-control-responsive'},
            'description': {'id': 'desX', 'style': 'width: 1200px; height: 30px; min-width: 300px; max-width: 100%;', 'class': 'form-control-responsive'},
            'min_order': {'id': 'minOrderField', 'style': 'width: 120px; height: 25px; min-width: 80px; max-width: 100%;', 'class': 'form-control-responsive'},
            'min_stock': {'id': 'minStockField', 'style': 'width: 120px; height: 25px; min-width: 80px; max-width: 100%;', 'class': 'form-control-responsive'},
            'unit_total_cost': {'id': 'id_unit_total_cost', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'retail_sell_multiplier': {'id': 'id_retail_sell_multiplier', 'style': 'width: 40px;','onchange': 'updateRetailSell()'},
            'builder_sell_multiplier': {'id': 'id_builder_sell_multiplier', 'style': 'width: 40px;','onchange': 'updateBuilderSell()'},
            'surplus_sell_multiplier': {'id': 'id_surplus_sell_multiplier', 'style': 'width: 40px;','onchange': 'updateSurplusSell()'},
            # Cost tab fields
            'unit_base_cost': {'id': 'id_unit_base_cost', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'unit_material_cost': {'id': 'id_unit_material_cost', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'bulk_material_cost': {'id': 'id_bulk_material_cost', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'bulk_qty': {'id': 'id_bulk_qty', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'unit_labor_minutes': {'id': 'id_unit_labor_minutes', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'bulk_labor_cost': {'id': 'id_bulk_labor_cost', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'unit_labor_cost': {'id': 'id_unit_labor_cost', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'bulk_total_cost': {'id': 'id_bulk_total_cost', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'unit_top_install_minutes': {'id': 'id_unit_top_install_minutes', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'retail_sell': {'id': 'id_retail_sell', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'builder_sell': {'id': 'id_builder_sell', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
            'surplus_sell': {'id': 'id_surplus_sell', 'style': 'width: 250px; min-width: 150px; max-width: 100%;', 'class': 'form-control-responsive'},
        }
        
        for field, attrs in field_attrs.items():
            self.fields[field].widget.attrs.update(attrs)

        # Add responsive CSS for all responsive fields
        responsive_fields = ['manufacturer', 'category', 'sub_category1', 'sub_category2', 'pref_vendor', 'alt_vendor', 'part_no', 'website', 'upc', 'product_lbl', 'description', 'width', 'height', 'depth', 'min_order', 'min_stock', 'unit_total_cost', 'unit_base_cost', 'unit_material_cost', 'bulk_material_cost', 'bulk_qty', 'unit_labor_minutes', 'bulk_labor_cost', 'unit_labor_cost', 'bulk_total_cost', 'unit_top_install_minutes', 'retail_sell', 'builder_sell', 'surplus_sell', 'unit_lead_time', 'bulk_lead_time']
        for field in responsive_fields:
            self.fields[field].widget.attrs['style'] += '; box-sizing: border-box;'
            
            # Add CSS classes for responsive behavior
            if 'class' in self.fields[field].widget.attrs:
                self.fields[field].widget.attrs['class'] += ' form-control-responsive'
            else:
                self.fields[field].widget.attrs['class'] = 'form-control-responsive'

        # No more common_fields since all cost fields are now responsive
    
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        images = self.cleaned_data.get('images')
        primary_image_id = self.cleaned_data.get('primary_image')

        if commit:
            instance.save()

            if images:
                # Ensure images is treated as a list, even if a single image is uploaded
                if not isinstance(images, list):
                    images = [images]
                for image in images:
                    ProductImage.objects.create(product=instance, image=image)

            # Set the primary image
            if primary_image_id:
                ProductImage.objects.filter(product=instance, is_primary=True).update(is_primary=False)  # Unset all primary images
                ProductImage.objects.filter(id=primary_image_id).update(is_primary=True)  # Set the selected one as primary

            # Handle accessories - this ensures they are preserved during updates
            if 'accessories' in self.cleaned_data:
                accessories_data = self.cleaned_data['accessories']
                if isinstance(accessories_data, list):
                    instance.accessories.set(accessories_data)
                else:
                    instance.accessories.clear()

            # Handle components - this ensures they are preserved during updates
            if 'components' in self.cleaned_data:
                # Parse components data that includes quantity information
                components_data = self.cleaned_data['components']
                if isinstance(components_data, str) and components_data:
                    # Parse the format "id:qty,id:qty,..."
                    component_relationships = []
                    for component_entry in components_data.split(','):
                        if ':' in component_entry:
                            component_id, qty = component_entry.split(':', 1)
                            try:
                                component_id = int(component_id.strip())
                                qty = float(qty.strip())
                                component_relationships.append((component_id, qty))
                            except (ValueError, TypeError):
                                continue
                        else:
                            # Handle legacy format without quantity
                            try:
                                component_id = int(component_entry.strip())
                                component_relationships.append((component_id, 1))
                            except (ValueError, TypeError):
                                continue
                    
                    # Clear existing components and add new ones with quantities
                    instance.components.clear()
                    from .models import ProductComponent
                    for component_id, qty in component_relationships:
                        try:
                            component = Product.objects.get(id=component_id)
                            ProductComponent.objects.create(product=instance, component=component, component_qty=qty)
                        except Product.DoesNotExist:
                            continue
                elif isinstance(components_data, list) and components_data:
                    # Handle case where components is a list of IDs (legacy format)
                    instance.components.set(components_data)
                else:
                    # Clear components if no valid data
                    instance.components.clear()

            self.save_m2m()

        return instance

    def clean(self):
        cleaned_data = super().clean()
        
        # Handle components field - keep as string for the save method to handle
        if 'components' in cleaned_data:
            components_value = cleaned_data.get('components')
            if isinstance(components_value, str) and components_value.strip() and components_value != 'none':
                # Keep as string for the save method to handle
                cleaned_data['components'] = components_value
        
        unit_material_cost = cleaned_data.get('unit_material_cost') or Decimal('0')
        unit_labor_cost = cleaned_data.get('unit_labor_cost') or Decimal('0')
        unit_base_cost = cleaned_data.get('unit_base_cost') or Decimal('0')
        retail_sell_multiplier = cleaned_data.get('retail_sell_multiplier')
        builder_sell_multiplier = cleaned_data.get('builder_sell_multiplier')
        surplus_sell_multiplier = cleaned_data.get('surplus_sell_multiplier') or Decimal('1')

        # Handle datetime parsing for datetime-local inputs
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone
        
        date_entered_str = cleaned_data.get('date_entered')
        if date_entered_str and isinstance(date_entered_str, str):
            # Parse the datetime-local format (YYYY-MM-DDTHH:MM)
            parsed_date = parse_datetime(date_entered_str)
            if parsed_date:
                cleaned_data['date_entered'] = parsed_date
            else:
                # If parsing fails, use current time
                cleaned_data['date_entered'] = timezone.now()
        
        date_updated_str = cleaned_data.get('date_updated')
        if date_updated_str and isinstance(date_updated_str, str):
            # Parse the datetime-local format (YYYY-MM-DDTHH:MM)
            parsed_date = parse_datetime(date_updated_str)
            if parsed_date:
                cleaned_data['date_updated'] = parsed_date
            else:
                # If parsing fails, use current time
                cleaned_data['date_updated'] = timezone.now()

        # unit_total_cost calculation: base cost + labor cost + material cost
        unit_total_cost = unit_base_cost + unit_labor_cost + unit_material_cost
        cleaned_data['unit_total_cost'] = unit_total_cost

        # retail_sell calculation - only if not manually entered
        if not cleaned_data.get('retail_sell') and retail_sell_multiplier and retail_sell_multiplier > 0:
            cleaned_data['retail_sell'] = unit_total_cost / retail_sell_multiplier

        # builder_sell calculation - only if not manually entered
        if not cleaned_data.get('builder_sell') and builder_sell_multiplier and builder_sell_multiplier > 0:
            cleaned_data['builder_sell'] = unit_total_cost / builder_sell_multiplier

        # surplus_sell calculation - only if not manually entered
        if not cleaned_data.get('surplus_sell') and surplus_sell_multiplier and surplus_sell_multiplier > 0:
            cleaned_data['surplus_sell'] = unit_total_cost / surplus_sell_multiplier

        return cleaned_data

class ProductAccessoryForm(forms.ModelForm):
    class Meta:
        model = ProductAccessory
        fields = ['accessory']

ProductAccessoryFormSet = inlineformset_factory(
    Product, 
    ProductAccessory, 
    form=ProductAccessoryForm, 
    extra=1, 
    can_delete=True,
    fk_name='product'  # Specify the foreign key name here
)

class ProductFilterForm(forms.Form):
    keyword = forms.CharField(label='Keyword', required=False)
    category = forms.ModelChoiceField(queryset=ProductCategory.objects.all(), empty_label='All Categories', required=False)
    subcategory1 = forms.ModelChoiceField(queryset=ProductSubCategory1.objects.all(), empty_label='All Subcategories Level 1', required=False)
    subcategory2 = forms.ModelChoiceField(queryset=ProductSubCategory2.objects.all(), empty_label='All Subcategories Level 2', required=False)
    
class ManufacturerForm(forms.ModelForm):
    class Meta:
        model = Manufacturer
        fields = [
            'manufacturer_name', 'address1', 'address2', 'city', 'state', 'zip',
            'order_phone','contact_name', 'contact_phone', 'contact_email',
            'comments', 'status', 'preferred_vendor','website'
        ]
        widgets = {
            'manufacturer_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'address1': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'address2': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'city': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'state': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'zip': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'order_phone': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control form-control-sm'}),
            'comments': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'status': forms.Select(choices=[(True, 'Active'), (False, 'Inactive')], attrs={'class': 'form-control form-control-sm'}),
            'preferred_vendor': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'website': forms.URLInput(attrs={'class': 'form-control form-control-sm'}),
        }
    

class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = [
            'vendor_no', 'vendor_name', 'address1', 'address2', 'city', 'state', 'zip',
            'order_phone', 'contact_name', 'contact_phone', 'contact_email',
            'delivery_days', 'delivery_charges', 'warehouse_address', 'warehouse_city',
            'warehouse_state', 'warehouse_zip', 'comments', 'status','website'
        ]
        widgets = {
            'vendor_no': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'vendor_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'address1': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'address2': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'city': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'state': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'zip': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'order_phone': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control form-control-sm'}),
            'delivery_days': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'delivery_charges': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'warehouse_address': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'warehouse_city': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'warehouse_state': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'warehouse_zip': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'comments': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
            'status': forms.Select(choices=[(True, 'Active'), (False, 'Inactive')], attrs={'class': 'form-control form-control-sm'}),
            'website': forms.URLInput(attrs={'class': 'form-control form-control-sm'}),
        }
        
class FinishForm(forms.ModelForm):
    class Meta:
        model = Finish
        fields = [
            'description', 'category', 'sub_category1', 'sub_category2', 'manufacturer', 'status', 'comments'
        ]
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'category': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'sub_category1': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'sub_category2': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'manufacturer': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'status': forms.Select(choices=[(True, 'Active'), (False, 'Inactive')], attrs={'class': 'form-control form-control-sm'}),
            'comments': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set alphabetical ordering for dropdown fields
        self.fields['category'].queryset = ProductCategory.objects.filter(status=True).order_by('product_category')
        self.fields['manufacturer'].queryset = Manufacturer.objects.filter(status=True).order_by('manufacturer_name')
        # sub_category1 and sub_category2 use ChainedForeignKey with sort=True, so they're already sorted

class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ['product_category']
        labels = {'product_category': 'Category Name'}
        widgets = {
            'product_category': forms.TextInput(attrs={'class': 'form-control form-control-sm'})
        }
        
class ProductSubCategory1Form(forms.ModelForm):
    class Meta:
        model = ProductSubCategory1
        fields = ['product_sub_category']
        labels = {'product_sub_category': 'Subcategory Name',}
        widgets = {
            'product_sub_category': forms.TextInput(attrs={'class': 'form-control form-control-sm'})
        }

class ProductSubCategory2Form(forms.ModelForm):
    class Meta:
        model = ProductSubCategory2
        fields = ['product_sub_category2']
        labels = {'product_sub_category2': 'Subcategory2 Name',}
        widgets = {
            'product_sub_category2': forms.TextInput(attrs={'class': 'form-control form-control-sm'})
        }
        
class ColorForm(forms.ModelForm):
    class Meta:
        model = Color
        fields = ['color_name']
        labels = {'color_name': 'Color Name'}
        widgets = {
            'color_name': forms.TextInput(attrs={'class': 'form-control form-control-sm'})
        }

class ProductQuoteForm(forms.ModelForm):
    class Meta:
        model = ProductQuote
        fields = ['name', 'customer', 'status', 'comments']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter quote name (optional)'}),
            'status': forms.Select(choices=[('A', 'Active'), ('I', 'Inactive')]),
            'comments': forms.Textarea(attrs={'rows': 4}),
        }
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Generate default name if not provided
        if not instance.name and instance.customer:
            instance.name = f"{instance.customer.first_name} {instance.customer.last_name} Quote"
        elif not instance.name:
            instance.name = f"Quote #{instance.id}" if instance.id else "New Quote"
        
        if commit:
            instance.save()
        return instance


class AdHocForm(forms.ModelForm):
    """Form for creating and editing Ad-Hoc items."""
    
    class Meta:
        model = AdHoc
        fields = ['part_no', 'description', 'category', 'retail_price', 'manufacturer', 'vendor', 'cost']
        widgets = {
            'part_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter part number',
                'style': 'width: 200px;'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter description',
                'style': 'width: 300px;'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'style': 'width: 200px;'
            }),
            'retail_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'style': 'width: 120px;'
            }),
            'manufacturer': forms.Select(attrs={
                'class': 'form-select',
                'style': 'width: 200px;'
            }),
            'vendor': forms.Select(attrs={
                'class': 'form-select',
                'style': 'width: 200px;'
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'style': 'width: 120px;'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make category, manufacturer, and vendor optional
        self.fields['category'].required = False
        self.fields['manufacturer'].required = False
        self.fields['vendor'].required = False
        self.fields['retail_price'].required = False
        self.fields['cost'].required = False
        
        # Set alphabetical ordering for dropdown fields
        self.fields['category'].queryset = ProductCategory.objects.filter(status=True).order_by('product_category')
        self.fields['manufacturer'].queryset = Manufacturer.objects.filter(status=True).order_by('manufacturer_name')
        self.fields['vendor'].queryset = Vendor.objects.filter(status=True).order_by('vendor_name')

class CostPoolForm(forms.ModelForm):
    class Meta:
        model = CostPool
        fields = ['manufacturer', 'category', 'sub_category1', 'sub_category2', 'retail', 'builder', 'surplus', 'status', 'date_entered', 'date_updated']
        widgets = {
            'manufacturer': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'category': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'sub_category1': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'sub_category2': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'date_entered': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
            'date_updated': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control form-control-sm'}),
            'retail': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0.01',
                'max': '1.00',
                'placeholder': '0.60'
            }),
            'builder': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0.01',
                'max': '1.00',
                'placeholder': '0.75'
            }),
            'surplus': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0.01',
                'max': '1.00',
                'placeholder': '0.50'
            }),
            'status': forms.Select(choices=[(True, 'Active'), (False, 'Inactive')], attrs={'class': 'form-control form-control-sm'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial values for new cost pools
        if not self.instance.pk:
            self.fields['retail'].initial = 0.60
            self.fields['builder'].initial = 0.75
            self.fields['surplus'].initial = 0.50
            self.fields['status'].initial = True
        else:
            # Format datetime values for HTML5 datetime-local input
            if self.instance.date_entered:
                self.fields['date_entered'].initial = self.instance.date_entered.strftime('%Y-%m-%dT%H:%M')
            if self.instance.date_updated:
                self.fields['date_updated'].initial = self.instance.date_updated.strftime('%Y-%m-%dT%H:%M')
        
        # Set alphabetical ordering for dropdown fields
        self.fields['manufacturer'].queryset = Manufacturer.objects.filter(status=True).order_by('manufacturer_name')
        self.fields['category'].queryset = ProductCategory.objects.filter(status=True).order_by('product_category')
        # sub_category1 and sub_category2 use ChainedForeignKey with sort=True, so they're already sorted
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Handle datetime parsing for datetime-local inputs
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone
        
        date_entered_str = cleaned_data.get('date_entered')
        if date_entered_str and isinstance(date_entered_str, str):
            # Parse the datetime-local format (YYYY-MM-DDTHH:MM)
            parsed_date = parse_datetime(date_entered_str)
            if parsed_date:
                cleaned_data['date_entered'] = parsed_date
            else:
                # If parsing fails, use current time
                cleaned_data['date_entered'] = timezone.now()
        
        date_updated_str = cleaned_data.get('date_updated')
        if date_updated_str and isinstance(date_updated_str, str):
            # Parse the datetime-local format (YYYY-MM-DDTHH:MM)
            parsed_date = parse_datetime(date_updated_str)
            if parsed_date:
                cleaned_data['date_updated'] = parsed_date
            else:
                # If parsing fails, use current time
                cleaned_data['date_updated'] = timezone.now()
        
        return cleaned_data