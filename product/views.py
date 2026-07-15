from collections import defaultdict
from decimal import Decimal
import json
import re
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from .decorators import role_permission_required
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, UpdateView, CreateView
from django.urls import reverse, reverse_lazy
from django.db.models import Q, Prefetch
from django.db.models.functions import Lower
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_GET, require_POST
from django.template.loader import render_to_string
from django.core.cache import cache
from django.conf import settings
from django.contrib import messages

# Import utility functions for PDF generation
from .utils import generate_quote_markdown, markdown_to_pdf, markdown_to_html

# Import mixins
from .mixins import ImageHandlingMixin, BreadcrumbMixin

# Utility function for common dropdown data fetching
def get_dropdown_data(model_class, name_field, status_field='status', cache_key_prefix='', additional_filters=None, order_by_field=None):
    """
    Generic utility function to fetch dropdown data with alphabetical sorting and caching.
    
    Args:
        model_class: The Django model class
        name_field: The field name to use for display (e.g., 'product_category', 'manufacturer_name')
        status_field: The status field name (default: 'status')
        cache_key_prefix: Prefix for cache key (e.g., 'categories', 'manufacturers')
        additional_filters: Dict of additional filters to apply
        order_by_field: Field to order by (defaults to name_field)
    
    Returns:
        JsonResponse with success status and data
    """
    if order_by_field is None:
        order_by_field = name_field
    
    cache_key = f'{cache_key_prefix}_dropdown_data'
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        try:
            queryset = model_class.objects.filter(**{status_field: True})
            
            if additional_filters:
                queryset = queryset.filter(**additional_filters)
            
            items = queryset.order_by(order_by_field).values('id', name_field)
            
            cached_data = {
                'success': True,
                'data': list(items)
            }
            
            # Cache for 1 hour
            cache.set(cache_key, cached_data, 3600)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse(cached_data)

# Model imports
from .models import (
    Product, ProductAccessory, ProductCategory, ProductImage, ProductQuote, ProductQuoteLine,
    ProductSubCategory1, ProductSubCategory2, Manufacturer,
    Vendor, Finish, AdHoc, AdHocQuoteLine, CostPool
)
from .forms import (
    ManufacturerForm, ProductForm, ProductQuoteForm,
    VendorForm, AdHocForm
)




class ProductCreateView(LoginRequiredMixin, ImageHandlingMixin, BreadcrumbMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'product/productform3.html'

    def get_success_url(self):
        return reverse('product:product-list')

    def form_valid(self, form):
        self.object = form.save()
        self.handle_product_images(form, self.object)
        messages.success(
            self.request,
            f'Product "{self.object.part_no}" created successfully.',
        )
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['manufacturers'] = Manufacturer.objects.all()  
        context['categories'] = ProductCategory.objects.all()
        context['action'] = 'Create'
        # For new products, we don't have category info yet, so no finishes to show
        context['finishes'] = []
        return context

    def get_breadcrumbs(self):
        return [
            self.get_home_breadcrumb(),
            self.get_product_breadcrumb(),
        ]

class ProductDuplicateUpdateView(LoginRequiredMixin, ImageHandlingMixin, BreadcrumbMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'product/productform3.html'

    def get_success_url(self):
        return reverse('product:product-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # If it's a new product (duplicated), we'll show the original product details
        original_product = self.get_original_product()
        context['product_id'] = original_product.id
        context['action'] = 'Duplicate and Update'  # Showing it's a duplication and update action
        context['original_product'] = original_product
        
        # Get finishes related to this product's category/subcategories
        finishes = Finish.objects.filter(
            category=original_product.category,
            sub_category1=original_product.sub_category1,
            sub_category2=original_product.sub_category2,
            status=True
        )
        context['finishes'] = finishes
        
        primary_image = original_product.images.filter(is_primary=True).first()
        context['primary_image'] = primary_image
        context['product'] = self.object
        return context

    def get_breadcrumbs(self):
        return [
            self.get_home_breadcrumb(),
            self.get_product_breadcrumb(),
        ]

    def get_object(self):
        """Override the get_object method to create a duplicate product"""
        # Get the original product
        original_product = self.get_original_product()
        print("Original product:", original_product)
        original_product_data = original_product.__dict__.copy()
        original_product_data.pop('id', None) 
        original_product_data.pop('_state', None)  # Remove internal _state attribute
        original_product_data.pop('description', None) 
        original_product_data.pop('date_entered', None)  
        original_product_data.pop('date_updated', None) 
        # Debug: 
        original_product_data['part_no'] = f"{original_product.part_no}-Copy"
        new_product = Product.objects.create(**original_product_data)
        print("New product created:", new_product)
        for image in original_product.images.all():
            ProductImage.objects.create(product=new_product, image=image.image)

        return new_product

    def get_original_product(self):
        """Helper function to get the original product"""
        product_uuid = self.kwargs.get('pk')
        return get_object_or_404(Product, uuid=product_uuid)

    def form_valid(self, form):
        original_product = self.get_original_product()
        duplicated_product = form.save(commit=False)
        self.handle_product_images(form, duplicated_product)
        duplicated_product.save()
        messages.success(
            self.request,
            f'Product "{duplicated_product.part_no}" created successfully.',
        )
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        print(form.errors)  # Debugging form errors
        return super().form_invalid(form)


class EditProductImagesView(LoginRequiredMixin, View):
    template_name = 'product/edit_product_images.html'

    def get(self, request, pk):
        product = get_object_or_404(Product, uuid=pk)
        images = ProductImage.objects.filter(product=product)
        return render(request, self.template_name, {'product': product, 'images': images})

    def post(self, request, pk):
        product = get_object_or_404(Product, uuid=pk)
        
        # Check if this is a delete request
        delete_image_id = request.POST.get('delete_image')
        if delete_image_id:
            try:
                image = ProductImage.objects.get(id=delete_image_id, product=product)
                if image.image:
                    image.image.delete(save=False)
                image.delete()
                messages.success(request, 'Image deleted successfully.')
            except ProductImage.DoesNotExist:
                messages.error(request, 'Image not found.')
            except Exception as e:
                messages.error(request, f'Error deleting image: {str(e)}')
            
            return redirect('product:product-update2', pk=product.uuid)
        
        # Handle primary and spec image updates
        primary_image_id = request.POST.get('primary_image')
        spec_image_ids = request.POST.getlist('spec_image')  # more spec

        if primary_image_id:
            ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
            ProductImage.objects.filter(id=primary_image_id).update(is_primary=True)

        if spec_image_ids:
            ProductImage.objects.filter(product=product, is_spec=True).update(is_spec=False)
            ProductImage.objects.filter(id__in=spec_image_ids).update(is_spec=True)

        return redirect('product:product-update2', pk=product.uuid)

@login_required
def view_product_images(request, pk):
    product = get_object_or_404(Product, uuid=pk)
    # Order images: primary first, then specs, then others
    images = product.images.all().order_by('-is_primary', '-is_spec', 'id')
    
    # Calculate image counts
    primary_count = images.filter(is_primary=True).count()
    spec_count = images.filter(is_spec=True).count()
    total_count = images.count()
    
    context = {
        'product': product, 
        'images': images,
        'primary_count': primary_count,
        'spec_count': spec_count,
        'total_count': total_count,
    }
    return render(request, 'product/view_product_images.html', context)
      
class ProductUpdateView2(LoginRequiredMixin, ImageHandlingMixin, BreadcrumbMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'product/productform3.html'
    
    def get_object(self, queryset=None):
        """Override to use uuid instead of pk"""
        uuid = self.kwargs.get('pk')
        return Product.objects.get(uuid=uuid)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product_id'] = self.object.id
        context['action'] = 'Update'
        context['product'] = self.object

        product = self.object
        # Get finishes related to this product's category/subcategories
        finishes = Finish.objects.filter(
            category=product.category,
            sub_category1=product.sub_category1,
            sub_category2=product.sub_category2,
            status=True
        )
        context['finishes'] = finishes
        primary_image = product.images.filter(is_primary=True).first()
        context['primary_image'] = primary_image 
        return context

    def get_success_url(self):
        return reverse('product:product-update2', kwargs={'pk': self.object.uuid})

    def form_valid(self, form):
        self.object = form.save()
        self.handle_product_images(form, self.object)
        messages.success(
            self.request,
            f'Product "{self.object.part_no}" updated successfully.',
        )
        return redirect(self.get_success_url())

    def get_breadcrumbs(self):
        return [
            self.get_home_breadcrumb(),
            self.get_product_breadcrumb(),
            {'name': 'Product Update', 'url': reverse('product:product-update2', args=[self.object.uuid]), 'position': 3, 'resolved': True},
            {'name': self.object.part_no, 'url': None, 'position': 4, 'resolved': False},
        ]
    
class ProductListView(LoginRequiredMixin, BreadcrumbMixin, ListView):
    model = Product
    template_name = 'product/product_list.html'
    context_object_name = 'products'
    paginate_by = 16  # Set pagination to 16 products per page

    def get_queryset(self):
        # Order by id for consistent pagination and prefetch related data
        return Product.objects.select_related(
            'category', 'sub_category1', 'sub_category2', 'manufacturer', 'pref_vendor', 'alt_vendor'
        ).prefetch_related(
            'images'
        ).order_by('id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add primary images to the context using prefetched data
        products_with_images = []
        for product in context['products']:
            # Use prefetched images to find primary image, or first image if no primary
            images = list(product.images.all())
            primary_image = next((img for img in images if img.is_primary), None)
            # If no primary image, use the first image if available
            if not primary_image and images:
                primary_image = images[0]
            products_with_images.append((product, primary_image))
        context['products_with_images'] = products_with_images

        # Cache the total count to avoid repeated queries
        total_count_cache_key = 'product_list_total_count'
        total_count = cache.get(total_count_cache_key)
        if total_count is None:
            total_count = Product.objects.count()
            cache.set(total_count_cache_key, total_count, 300)  # Cache for 5 minutes
        context['total_count'] = total_count
        
        # page_obj is already in context from ListView, but ensure it's there
        context['page_obj'] = context.get('page_obj', self.get_queryset())
        return context

    def get_breadcrumbs(self):
        return [
            self.get_home_breadcrumb(),
            self.get_product_breadcrumb(),
            {'name': 'Product List', 'url': None, 'position': 3, 'resolved': False},
        ]


class ProductDetail2View(LoginRequiredMixin, BreadcrumbMixin, DetailView):
    model = Product
    template_name = 'product/tablist - Copy.html'
    context_object_name = 'product'
    
    def get_object(self, queryset=None):
        """Override to use uuid instead of pk"""
        uuid = self.kwargs.get('pk')
        return Product.objects.get(uuid=uuid)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch product components and accessories
        context['components'] = self.object.product_components.all()
        context['accessories'] = self.object.accessories.all()
        context['primary_image'] = self.object.images.filter(is_primary=True).first()
        return context

    def get_breadcrumbs(self):
        return [
            self.get_home_breadcrumb(),
            self.get_product_breadcrumb(),
            self.get_product_list_breadcrumb(),
            {'name': self.object.part_no, 'url': None, 'position': 4, 'resolved': False},
        ]
    

@login_required
@require_POST
def product_delete(request, pk):
    """Delete a product after POST confirmation from the product list."""
    product = get_object_or_404(Product, uuid=pk)
    part_no = product.part_no or product.pk
    product.delete()
    messages.success(request, f'Product "{part_no}" deleted successfully.')
    return redirect('product:product-list')


@login_required
def load_subcategories(request):
    """Optimized subcategories loading with caching"""
    category_id = request.GET.get('category')
    
    # Cache key for this category's subcategories
    cache_key = f'subcategories_{category_id}'
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        # Use select_related to optimize queries
        subcategories1 = list(
            ProductSubCategory1.objects.filter(
                category_id=category_id, 
                status=True
            ).values('id', 'product_sub_category')
        )
        subcategories2 = list(
            ProductSubCategory2.objects.filter(
                sub_category1__category_id=category_id,
                status=True
            ).values('id', 'product_sub_category2')
        )
        cached_data = {
            'subcategories1': subcategories1, 
            'subcategories2': subcategories2
        }
        # Cache for 1 hour
        cache.set(cache_key, cached_data, 3600)
    
    return JsonResponse(cached_data)

@login_required
def load_related_products(request):
    description = request.GET.get('description')
    part_no = request.GET.get('part_no')
    
    products = Product.objects.all()
    
    if description:
        products = products.filter(description__icontains=description)
    
    if part_no:
        products = products.filter(part_no__icontains=part_no)
    
    product_list = list(products.values('id', 'description', 'part_no'))
    
    return JsonResponse({'products': product_list})

@login_required
def manufacturer_list(request):
    # Check if status filter is applied
    status_filter = request.GET.get('status', 'active')
    
    # Retrieve manufacturers based on status filter
    if status_filter == 'active':
        manufacturers_list = Manufacturer.objects.filter(status=True).order_by('manufacturer_name')
    elif status_filter == 'inactive':
        manufacturers_list = Manufacturer.objects.filter(status=False).order_by('manufacturer_name')
    else:  # 'all' or any other value
        manufacturers_list = Manufacturer.objects.all().order_by('manufacturer_name')
    
    # Pagination
    paginator = Paginator(manufacturers_list, 16)  # 16 manufacturers per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get counts for different statuses
    total_manufacturers = Manufacturer.objects.count()
    active_manufacturers = Manufacturer.objects.filter(status=True).count()
    inactive_manufacturers = Manufacturer.objects.filter(status=False).count()
    
    return render(request, 'product/manufacturers.html', {
        'manufacturers': page_obj, 
        'page_obj': page_obj,
        'paginator': paginator,
        'total_manufacturers': total_manufacturers,
        'active_manufacturers': active_manufacturers,
        'inactive_manufacturers': inactive_manufacturers
    })

@login_required
def create_manufacturer(request):
    """Create a new manufacturer using the edit_manufacturer template"""
    if request.method == "POST":
        form = ManufacturerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product:manufacturers')  # Redirect to manufacturer list after saving
    else:
        form = ManufacturerForm()

    # Create a dummy manufacturer object for the template
    dummy_manufacturer = type('DummyManufacturer', (), {
        'id': None,
        'manufacturer_name': 'New Manufacturer'
    })()

    return render(request, 'product/edit_manufacturer.html', {
        'form': form, 
        'manufacturer': dummy_manufacturer, 
        'is_view_mode': False
    })

@login_required
def edit_manufacturer(request, manufacturer_uuid):
    manufacturer = get_object_or_404(Manufacturer, uuid=manufacturer_uuid)
    
    # Check if this is view mode or edit mode
    is_view_mode = request.GET.get('mode') == 'view'
    
    # Handle form submission (only in edit mode)
    if request.method == "POST" and not is_view_mode:
        form = ManufacturerForm(request.POST, instance=manufacturer)
        if form.is_valid():
            form.save()
            return redirect('product:manufacturers') 
    else:
        form = ManufacturerForm(instance=manufacturer)

    return render(request, 'product/edit_manufacturer.html', {
        'form': form, 
        'manufacturer': manufacturer, 
        'is_view_mode': is_view_mode
    })

@login_required
def vendor_list(request):
    # Check if status filter is applied
    status_filter = request.GET.get('status', 'active')
    
    # Retrieve vendors based on status filter
    if status_filter == 'active':
        vendors_list = Vendor.objects.filter(status=True).order_by('vendor_name')
    elif status_filter == 'inactive':
        vendors_list = Vendor.objects.filter(status=False).order_by('vendor_name')
    else:  # 'all' or any other value
        vendors_list = Vendor.objects.all().order_by('vendor_name')
    
    # Pagination
    paginator = Paginator(vendors_list, 16)  # 16 vendors per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts for different statuses
    total_vendors = Vendor.objects.count()
    active_vendors = Vendor.objects.filter(status=True).count()
    inactive_vendors = Vendor.objects.filter(status=False).count()
    
    return render(request, 'product/vendors.html', {
        'vendors': page_obj, 
        'page_obj': page_obj,
        'paginator': paginator,
        'total_vendors': total_vendors,
        'active_vendors': active_vendors,
        'inactive_vendors': inactive_vendors
    })

@login_required
def create_vendor(request):
    """Create a new vendor using the edit_vendor template"""
    if request.method == "POST":
        form = VendorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product:vendors')  # Redirect to vendor list after saving
    else:
        form = VendorForm()

    # Create a dummy vendor object for the template
    dummy_vendor = type('DummyVendor', (), {
        'id': None,
        'vendor_name': 'New Vendor'
    })()

    return render(request, 'product/edit_vendor.html', {
        'form': form, 
        'vendor': dummy_vendor, 
        'is_view_mode': False
    })

@login_required
def edit_vendor(request, vendor_uuid):
    # Get the vendor instance
    vendor = get_object_or_404(Vendor, uuid=vendor_uuid)
    
    # Check if this is view mode or edit mode
    is_view_mode = request.GET.get('mode') == 'view'
    
    # Handle form submission (only in edit mode)
    if request.method == "POST" and not is_view_mode:
        form = VendorForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            return redirect('product:vendors')  # Redirect to vendor list after saving
    else:
        form = VendorForm(instance=vendor)

    return render(request, 'product/edit_vendor.html', {
        'form': form, 
        'vendor': vendor, 
        'is_view_mode': is_view_mode
    })

@login_required
@require_POST
def ajax_delete_vendor(request, pk):
    """AJAX delete vendor"""
    try:
        vendor = Vendor.objects.get(uuid=pk)
        vendor.delete()
        return JsonResponse({'success': True})
    except Vendor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vendor not found'}, status=404)

@login_required
@require_GET
def ajax_search_vendors(request):
    """AJAX search vendors with pagination and status filtering"""
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')
    page = request.GET.get('page', 1)
    
    # Debug logging
    print(f"Search request - Query: '{query}', Status: {status_filter}, Page: {page}")
    
    vendors = Vendor.objects.all()
    
    # Apply status filter
    if status_filter == 'active':
        vendors = vendors.filter(status=True)
        print(f"Filtering for active vendors: {vendors.count()} found")
    elif status_filter == 'inactive':
        vendors = vendors.filter(status=False)
        print(f"Filtering for inactive vendors: {vendors.count()} found")
    elif status_filter == 'all':
        print(f"Showing all vendors: {vendors.count()} found")
    # For 'all', no additional filter is applied
    
    if query:
        # Search either vendor_name OR vendor_no (either can contain the query)
        vendors = vendors.filter(
            Q(vendor_name__icontains=query) | Q(vendor_no__icontains=query)
        )
    
    # Pagination for search results
    paginator = Paginator(vendors, 16)  # 16 items per page
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    results = []
    for vendor in page_obj:
        # All users have full access - no permission checks
        result = {
            'id': str(vendor.uuid),
            'vendor_name': vendor.vendor_name,
            'contact_name': vendor.contact_name or '',
            'city': vendor.city or '',
            'vendor_no': vendor.vendor_no or '',
            'order_phone': vendor.order_phone or '',
            'contact_phone': vendor.contact_phone or '',
            'contact_email': vendor.contact_email or '',
            'status': vendor.status,
            'can_edit': True,
            'can_delete': True,
            'edit_url': reverse('product:edit_vendor', args=[vendor.uuid]),
            'delete_url': reverse('product:ajax_delete_vendor', args=[vendor.uuid])
        }
            
        results.append(result)
    
    return JsonResponse({
        'vendors': results,
        'paginator': {
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'page_range': list(paginator.page_range),
            'current_page': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        }
    })


@login_required
@require_GET
def ajax_filter_vendors_by_status(request):
    """AJAX filter vendors by status only with pagination"""
    status_filter = request.GET.get('status', 'false')
    page = request.GET.get('page', 1)
    
    # This function is only used for inactive vendors now
    if status_filter == 'false':
        vendors = Vendor.objects.filter(status=False)
    else:
        vendors = Vendor.objects.none()
    
    # Pagination for status filter results
    paginator = Paginator(vendors, 16)  # 16 items per page
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    results = []
    for vendor in page_obj:
        results.append({
            'id': str(vendor.uuid),
            'vendor_name': vendor.vendor_name,
            'contact_name': vendor.contact_name or '',
            'city': vendor.city or '',
            'vendor_no': vendor.vendor_no or '',
            'order_phone': vendor.order_phone or '',
            'contact_phone': vendor.contact_phone or '',
            'contact_email': vendor.contact_email or '',
            'status': vendor.status,
            'edit_url': reverse('product:edit_vendor', args=[vendor.uuid]),
            'delete_url': reverse('product:ajax_delete_vendor', args=[vendor.uuid]),
        })
    
    return JsonResponse({
        'vendors': results,
        'paginator': {
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'page_range': list(paginator.page_range),
            'current_page': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        }
    })

@login_required
@require_POST
def ajax_delete_manufacturer(request, pk):
    """AJAX delete manufacturer"""
    try:
        manufacturer = Manufacturer.objects.get(uuid=pk)
        manufacturer.delete()
        return JsonResponse({'success': True})
    except Manufacturer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Manufacturer not found'}, status=404)

@login_required
@require_GET
def ajax_search_manufacturers(request):
    """AJAX search manufacturers with pagination and status filtering"""
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')
    page = request.GET.get('page', 1)
    
    # Debug logging
    print(f"Manufacturer search request - Query: '{query}', Status: {status_filter}, Page: {page}")
    
    manufacturers = Manufacturer.objects.all()
    
    # Apply status filter
    if status_filter == 'active':
        manufacturers = manufacturers.filter(status=True)
        print(f"Filtering for active manufacturers: {manufacturers.count()} found")
    elif status_filter == 'inactive':
        manufacturers = manufacturers.filter(status=False)
        print(f"Filtering for inactive manufacturers: {manufacturers.count()} found")
    elif status_filter == 'all':
        print(f"Showing all manufacturers: {manufacturers.count()} found")
    # For 'all', no additional filter is applied
    
    if query:
        manufacturers = manufacturers.filter(
            Q(manufacturer_name__icontains=query)
        )
    
    # Pagination for search results
    paginator = Paginator(manufacturers, 16)  # 16 items per page
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    results = []
    for manufacturer in page_obj:
        results.append({
            'id': str(manufacturer.uuid),
            'manufacturer_name': manufacturer.manufacturer_name,
            'contact_name': manufacturer.contact_name or '',
            'city': manufacturer.city or '',
            'state': manufacturer.state or '',
            'order_phone': manufacturer.order_phone or '',
            'website': manufacturer.website or '',
            'status': manufacturer.status,
            'edit_url': reverse('product:edit_manufacturer', args=[manufacturer.uuid]),
            'delete_url': reverse('product:ajax_delete_manufacturer', args=[manufacturer.uuid]),
        })
    
    return JsonResponse({
        'manufacturers': results,
        'paginator': {
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'page_range': list(paginator.page_range),
            'current_page': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        }
    })


@login_required
@require_GET
def ajax_filter_manufacturers_by_status(request):
    """AJAX filter manufacturers by status only with pagination"""
    status_filter = request.GET.get('status', 'false')
    page = request.GET.get('page', 1)
    
    # This function is only used for inactive manufacturers now
    if status_filter == 'false':
        manufacturers = Manufacturer.objects.filter(status=False)
    else:
        manufacturers = Manufacturer.objects.none()
    
    # Pagination for status filter results
    paginator = Paginator(manufacturers, 16)  # 16 items per page
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    results = []
    for manufacturer in page_obj:
        results.append({
            'id': str(manufacturer.uuid),
            'manufacturer_name': manufacturer.manufacturer_name,
            'contact_name': manufacturer.contact_name or '',
            'city': manufacturer.city or '',
            'state': manufacturer.state or '',
            'order_phone': manufacturer.order_phone or '',
            'website': manufacturer.website or '',
            'status': manufacturer.status,
            'edit_url': reverse('product:edit_manufacturer', args=[manufacturer.uuid]),
            'delete_url': reverse('product:ajax_delete_manufacturer', args=[manufacturer.uuid]),
        })
    
    return JsonResponse({
        'manufacturers': results,
        'paginator': {
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'page_range': list(paginator.page_range),
            'current_page': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        }
    })


def search_accessories(request):
    query = request.GET.get('q', '')  
    filterby = request.GET.get('filterby', 'part_no') 

    if filterby == 'part_no':
        products = Product.objects.filter(
            part_no__icontains=query,
            product_type__in=['product', 'assembly']
        )
    elif filterby == 'description':
        products = Product.objects.filter(
            description__icontains=query,
            product_type__in=['product', 'assembly']
        )
    else:
        products = Product.objects.none()  

    results = [
        {'id': product.id, 'part_no': product.part_no, 'description': product.description, 'unit_total_cost': product.unit_total_cost,}
        for product in products
    ]

    return JsonResponse({'results': results})

def search_components(request):
    query = request.GET.get('q', '')  
    filterby = request.GET.get('filterby', 'part_no') 

    if filterby == 'part_no':
        products = Product.objects.filter(
            part_no__icontains=query
        )
    elif filterby == 'description':
        products = Product.objects.filter(
            description__icontains=query
        )
    else:
        products = Product.objects.none()  

    results = [
        {'id': product.id, 'part_no': product.part_no, 'description': product.description, 'unit_total_cost': product.unit_total_cost, 'product_type': product.product_type}
        for product in products
    ]

    return JsonResponse({'results': results})

@csrf_exempt
def add_accessories(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        accessories_ids = data.get('accessories', [])

        if not product_id or not accessories_ids:
            return JsonResponse({'success': False, 'error': 'Invalid product or accessory IDs'}, status=400)

        product = get_object_or_404(Product, id=product_id)
        accessories = Product.objects.filter(id__in=accessories_ids)

        for accessory in accessories:
            ProductAccessory.objects.create(product=product, accessory=accessory)
        
        return JsonResponse({'success': True})

    return JsonResponse({'success': False}, status=400)

@csrf_exempt
def remove_accessory(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        accessory_id = data.get('accessory_id')

        if not product_id or not accessory_id:
            return JsonResponse({'success': False, 'error': 'Invalid product or accessory ID'}, status=400)

        try:
            # Find and delete the ProductAccessory relationship
            ProductAccessory.objects.filter(product_id=product_id, accessory_id=accessory_id).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False}, status=400)

@csrf_exempt
def remove_component(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        component_id = data.get('component_id')

        if not product_id or not component_id:
            return JsonResponse({'success': False, 'error': 'Invalid product or component ID'}, status=400)

        try:
            # Find and delete the ProductComponent relationship
            from .models import ProductComponent
            ProductComponent.objects.filter(product_id=product_id, component_id=component_id).delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False}, status=400)

def _serialize_assembly_components(product):
    """Build JSON rows + hidden field value for the Edit Product components tab."""
    from .models import ProductComponent
    rows = []
    hidden_parts = []
    for pc in (
        ProductComponent.objects.filter(product=product)
        .select_related('component')
        .order_by('component__part_no')
    ):
        c = pc.component
        rows.append({
            'component_id': c.id,
            'part_no': c.part_no or '',
            'description': c.description or '',
            'product_type': c.product_type or '',
            'unit_total_cost': float(c.unit_total_cost) if c.unit_total_cost is not None else None,
            'qty': str(pc.component_qty),
        })
        hidden_parts.append(f'{c.id}:{pc.component_qty}')
    hidden = ','.join(hidden_parts) if hidden_parts else 'none'
    return rows, hidden


@csrf_exempt
def add_components(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        components_data = data.get('components', [])

        if not product_id or not components_data:
            return JsonResponse({'success': False, 'error': 'Invalid product or component data'}, status=400)

        try:
            try:
                product_id = int(product_id)
            except (TypeError, ValueError):
                return JsonResponse({'success': False, 'error': 'Invalid product id'}, status=400)

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return JsonResponse(
                    {'success': False, 'error': 'No Product matches the given query.'},
                    status=404,
                )

            from .models import ProductComponent

            added_components = []
            skipped_components = []

            for component_data in components_data:
                if isinstance(component_data, dict):
                    raw_id = component_data.get('id')
                    qty_raw = component_data.get('qty', 1)
                else:
                    raw_id = component_data
                    qty_raw = 1

                try:
                    component_id = int(raw_id)
                except (TypeError, ValueError):
                    continue

                try:
                    qty = Decimal(str(qty_raw))
                except Exception:
                    qty = Decimal('1')
                if qty <= 0:
                    continue

                try:
                    component = Product.objects.get(id=component_id)
                except Product.DoesNotExist:
                    return JsonResponse(
                        {'success': False, 'error': f'No product found for component id {component_id}.'},
                        status=400,
                    )

                if component_id == product_id:
                    return JsonResponse(
                        {'success': False, 'error': 'A product cannot be a component of itself.'},
                        status=400,
                    )

                existing_component = ProductComponent.objects.filter(
                    product=product,
                    component=component,
                ).first()

                if existing_component:
                    old_qty = existing_component.component_qty
                    existing_component.component_qty += qty
                    existing_component.save()
                    skipped_components.append(
                        f'{component.part_no} (+{qty} to existing {old_qty}, total {existing_component.component_qty})'
                    )
                else:
                    ProductComponent.objects.create(
                        product=product,
                        component=component,
                        component_qty=qty,
                    )
                    added_components.append(component.part_no)

            rows, hidden = _serialize_assembly_components(product)
            response_data = {
                'success': True,
                'selected_components': rows,
                'components_hidden': hidden,
            }
            if added_components:
                response_data['added'] = added_components
            if skipped_components:
                response_data['skipped'] = skipped_components

            return JsonResponse(response_data)

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'success': False}, status=400)

@login_required
def product_quote_list(request):
    """View to list product quotes with the option to use original or current prices."""
    from crm.models import Customer
    price_mode = request.GET.get('price_mode', 'original')  # Default to 'original'
    quotes = ProductQuote.objects.prefetch_related('line_items__product')  # Optimize queries
    customers = Customer.objects.all()
    return render(request, 'product/product_quote_list.html', {
        'quotes': quotes,
        'price_mode': price_mode,
        'customers': customers,
    })
    
def update_quote(request, quote_id):
    """View to update a product quote."""
    quote = get_object_or_404(ProductQuote, id=quote_id)

    breadcrumbs = [
        {'name': 'Home', 'url': reverse('home'), 'position': 1, 'resolved': True},
        {'name': 'Product', 'url': reverse('product:product-list'), 'position': 2, 'resolved': True},
        {'name': 'Quotes', 'url': reverse('product:product_quote_list'), 'position': 3, 'resolved': True},
        {'name': f'Update Quote for {quote.customer}', 'url': reverse('product:quote_update', args=[quote.id]), 'position': 4, 'resolved': True},
    ]
    
    if request.method == "POST":
        form = ProductQuoteForm(request.POST, instance=quote)
        if form.is_valid():
            form.save()
            return redirect('product:product_quote_list') 
    else:
        form = ProductQuoteForm(instance=quote)

    return render(request, 'product/update_quote.html', {'form': form, 'breadcrumbs':breadcrumbs})

def update_quote_price_type(request, quote_id):
    """View to update the price type of a quote."""
    quote = get_object_or_404(ProductQuote, id=quote_id)
    
    if request.method == "POST":
        price_type = request.POST.get('price_type')
        if price_type in ['retail_sell', 'builder_sell', 'surplus_sell']:
            quote.price_type = price_type
            quote.save()
            messages.success(request, f'Quote pricing type updated to {price_type.replace("_", " ").title()}')
        else:
            messages.error(request, 'Invalid price type selected')
    
    return redirect('product:quote_products', quote_id=quote.id)

def delete_quote(request, quote_id):
    """View to delete a product quote."""
    quote = get_object_or_404(ProductQuote, id=quote_id)

    breadcrumbs = [
        {'name': 'Home', 'url': reverse('home'), 'position': 1, 'resolved': True},
        {'name': 'Product', 'url': reverse('product:product-list'), 'position': 2, 'resolved': True},
        {'name': 'Quotes', 'url': reverse('product:product_quote_list'), 'position': 3, 'resolved': True},
        {'name': f'Delete Quote for {quote.customer}', 'url': reverse('product:delete_quote', args=[quote.id]), 'position': 4, 'resolved': True},
    ]
    
    if request.method == "POST":
        quote.delete()
        return redirect('product:product_quote_list')  

    return render(request, 'product/confirm_delete.html', {'quote': quote,'breadcrumbs':breadcrumbs})

def product_quote_pdf(request, quote_id):
    """Generate PDF for product quote with same header/footer as job print preview"""
    from product.pdf_generator import product_quote_pdf_generate
    return product_quote_pdf_generate(request, quote_id)


def add_product(request, quote_id, product_id):
    """View to add a product to a quote."""
    quote = get_object_or_404(ProductQuote, id=quote_id)
    product = get_object_or_404(Product, uuid=product_id)

    if request.method == "POST":
        quantity = int(request.POST.get('quantity', 1))  # Get quantity from the form
        price_type = request.POST.get('price_type', 'retail_sell')  # Get price type from the form
        line_item, created = ProductQuoteLine.objects.get_or_create(
            quote=quote,
            product=product,
            defaults={
                'quantity': quantity,
                'price_type': price_type,
                'product_description': product.description,
            }
        )
        if not created:
            # If the product already exists in the quote, update the quantity
            line_item.quantity += quantity
            line_item.save()

        quote.calculate_subtotal()
        return redirect('product:product_quote_list')
    
def delete_product(request, quote_id, line_item_id):
    """View to delete a product from a quote."""
    quote = get_object_or_404(ProductQuote, id=quote_id)
    line_item = get_object_or_404(ProductQuoteLine, id=line_item_id, quote=quote)

    if request.method == "POST":
        line_item.delete()

        quote.calculate_subtotal()
        return redirect('product:quote_products', quote_id=quote.id)  # Redirect to the same quote's products page
    
def edit_quantity(request, line_item_id):
    """
    View to edit the quantity of a product in a quote.
    """
    if request.method == "POST":
        line_item = get_object_or_404(ProductQuoteLine, id=line_item_id)
        
        # Handle both form data and JSON data
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                new_quantity = data.get("quantity", 0)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
        else:
            new_quantity = request.POST.get("quantity", 0)

        # Ensure the quantity is valid
        try:
            line_item.quantity = max(0, int(new_quantity))  # Prevent negative quantities
            line_item.save()
            
            # Return JSON response for AJAX requests
            if request.content_type == 'application/json':
                return JsonResponse({'success': True, 'quantity': line_item.quantity})
                
        except ValueError:
            if request.content_type == 'application/json':
                return JsonResponse({'error': 'Invalid quantity'}, status=400)
            pass 

        return redirect('product:product_quote_list')
    
def add_product_quote(request, job_id=None):
    """View to add a new product quote."""
    if request.method == "POST":
        form = ProductQuoteForm(request.POST)
        if form.is_valid():
            quote = form.save()
            # If job_id is provided, redirect to job detail page
            if job_id:
                return redirect('job:job_detail', pk=job_id)
            else:
                return redirect('product:product_quote_list')  
    else:
        form = ProductQuoteForm()

    return render(request, 'product/add_product_quote.html', {'form': form, 'job_id': job_id})

def quote_products(request, quote_id):
    """View to manage products in a quote and allow searching for new products."""
    from django.db.models import Prefetch
    from product.models import ProductImage
    quote = get_object_or_404(ProductQuote, id=quote_id)

    # Get associated jobs for this quote (now direct relationship)
    from job.models import Job
    associated_jobs = Job.objects.filter(product_quotes=quote).select_related('customer')

    # Prepare line items with primary images (optimized)
    line_items = list(
        quote.line_items.select_related('product').prefetch_related(
            Prefetch(
                'product__images',
                queryset=ProductImage.objects.filter(is_primary=True),
                to_attr='primary_images'
            )
        )
    )
    line_items_with_images = []
    for line_item in line_items:
        primary_images = getattr(line_item.product, 'primary_images', [])
        primary_image = primary_images[0] if primary_images else None
        line_items_with_images.append((line_item, primary_image))
    
    # Prepare ad-hoc line items
    adhoc_line_items = list(quote.adhoc_line_items.select_related('adhoc'))

    # Initialize querysets for the search
    products = Product.objects.all()
    categories = ProductCategory.objects.all()
    sub_categories1 = ProductSubCategory1.objects.all()
    sub_categories2 = ProductSubCategory2.objects.all()
    manufacturers = Manufacturer.objects.all()
    vendors = Vendor.objects.all()

    # Handle search filters
    keywords = request.GET.get('keywords')
    category = request.GET.get('category')
    sub_category1 = request.GET.get('sub_category1')
    sub_category2 = request.GET.get('sub_category2')
    manufacturer = request.GET.get('manufacturer')
    active_status = request.GET.get('active_status')
    is_ajax = request.GET.get('ajax') == '1'
    sort = request.GET.get('sort')
    order = request.GET.get('order', 'asc')

    # Only show products when search filters are applied
    if any([keywords, category, sub_category1, sub_category2, manufacturer, active_status]):
        if keywords:
            products = products.filter(
                Q(part_no__icontains=keywords) |
                Q(description__icontains=keywords)
            )
        if category:
            products = products.filter(category_id=category)
        if sub_category1:
            products = products.filter(sub_category1_id=sub_category1)
        if sub_category2:
            products = products.filter(sub_category2_id=sub_category2)
        if manufacturer:
            products = products.filter(manufacturer_id=manufacturer)
        if active_status == 'True':
            products = products.filter(status=True)
        elif active_status == 'False':
            products = products.filter(status=False)

        # Optional sorting
        if sort == 'name':
            products = products.order_by('-part_no' if order == 'desc' else 'part_no')
        elif sort == 'retail_price':
            products = products.order_by('-retail_sell' if order == 'desc' else 'retail_sell')
        elif sort == 'builder_price':
            products = products.order_by('-builder_sell' if order == 'desc' else 'builder_sell')

        products = products.prefetch_related(
            Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_primary=True),
                to_attr='primary_images'
            )
        )

        # Apply pagination
        paginator = Paginator(products, 10)  
        page_number = request.GET.get('page') 
        page_obj = paginator.get_page(page_number) 

        # Prepare products_with_images for the search results
        products_with_images = []
        for product in page_obj:
            primary_images = getattr(product, 'primary_images', [])
            primary_image = primary_images[0] if primary_images else None
            products_with_images.append((product, primary_image))
    else:
        # No filters applied - show empty results
        products_with_images = []
        page_obj = None

    if is_ajax:
        html = render_to_string('product/_quote_product_search_table.html', {
            'products_with_images': products_with_images,
            'page_obj': page_obj,
            'quote': quote,
            'request': request,
            'is_ajax': True,
            'sort': sort,
            'order': order,
        })
        return HttpResponse(html)

    return render(
        request,
        'product/quote_products.html',
        {
            'quote': quote,
            'page_obj': page_obj,
            'categories': categories, 
            'sub_categories1': sub_categories1,
            'sub_categories2': sub_categories2,
            'manufacturers': manufacturers,
            'line_items_with_images': line_items_with_images,
            'adhoc_line_items': adhoc_line_items,
            'products_with_images': products_with_images,
            'is_ajax': is_ajax,
            'associated_jobs': associated_jobs,
            'vendors': vendors,
            'sort': sort,
            'order': order,
        }
    )
    
def add_multiple_products(request, quote_id):
    """View to add multiple products to a quote."""
    quote = get_object_or_404(ProductQuote, id=quote_id)

    if request.method == "POST":
        quantities = {}
        price_types = {}

        for key, value in request.POST.items():
            match = re.match(r'quantities\[(\d+)\]', key)
            if match:
                try:
                    quantities[int(match.group(1))] = int(value or 0)
                except (TypeError, ValueError):
                    quantities[int(match.group(1))] = 0

            match = re.match(r'price_types\[(\d+)\]', key)
            if match:
                price_types[int(match.group(1))] = value

        # Add only products with quantity > 0 (no checkbox selection required)
        for product_id, quantity in quantities.items():
            if quantity <= 0:
                continue
            product = get_object_or_404(Product, id=product_id)
            price_type = price_types.get(product.id, 'retail_sell')
            line_item, created = ProductQuoteLine.objects.get_or_create(
                quote=quote,
                product=product,
                defaults={
                    'quantity': quantity,
                    'price_type': price_type,
                    'product_description': product.description,
                }
            )
            if not created:
                line_item.quantity += quantity
                line_item.save()

        quote.calculate_subtotal()

    return redirect('product:quote_products', quote_id=quote.id)

def ajax_vendors(request):
    q = request.GET.get('q', '')
    vendors = Vendor.objects.all()
    if q:
        vendors = vendors.filter(
            Q(vendor_name__icontains=q) |
            Q(contact_name__icontains=q) |
            Q(city__icontains=q)
        )
    data = {
        'vendors': [
            {
                'id': v.id,
                'vendor_name': v.vendor_name,
                'contact_name': v.contact_name,
                'city': v.city,
            } for v in vendors
        ]
    }
    return JsonResponse(data)

def ajax_manufacturers(request):
    q = request.GET.get('q', '')
    manufacturers = Manufacturer.objects.all()
    if q:
        manufacturers = manufacturers.filter(
            Q(manufacturer_name__icontains=q) |
            Q(contact_name__icontains=q) |
            Q(city__icontains=q)
        )
    data = {
        'manufacturers': [
            {
                'id': m.id,
                'manufacturer_name': m.manufacturer_name,
                'contact_name': m.contact_name,
                'city': m.city,
                'state': m.state,
                'order_phone': m.order_phone,
                'website': m.website,
            } for m in manufacturers
        ]
    }
    return JsonResponse(data)

@require_GET
def ajax_product_quotes(request):
    """AJAX endpoint to search product quotes by customer name or quote fields."""
    query = request.GET.get('q', '').strip()
    price_mode = request.GET.get('price_mode', 'original')
    quotes = ProductQuote.objects.prefetch_related('line_items__product')
    if query:
        quotes = quotes.filter(
            Q(customer__first_name__icontains=query) |
            Q(customer__last_name__icontains=query) |
            Q(name__icontains=query)
        )
    results = []
    for quote in quotes:
        customer_name = f"{quote.customer.first_name if quote.customer else ''} {quote.customer.last_name if quote.customer else ''}".strip() or "No Customer"
        quote_name = quote.name if quote.name else f"Quote #{quote.id}"
        results.append({
            'id': quote.id,
            'name': quote_name,
            'customer': customer_name,
            'update_url': reverse('product:quote_update', args=[quote.id]),
            'products_url': reverse('product:quote_products', args=[quote.id]),
            'delete_url': reverse('product:delete_quote', args=[quote.id]),
            'pdf_url': reverse('product:product_quote_pdf', args=[quote.id]),
        })
    return JsonResponse({'results': results})




@require_GET
def ajax_categories(request):
    """Optimized categories loading with caching"""
    response = get_dropdown_data(
        model_class=ProductCategory,
        name_field='product_category',
        cache_key_prefix='all_categories'
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'categories': [{'id': item['id'], 'name': item['product_category']} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response

@require_GET
def ajax_subcat1(request, category_id):
    """Optimized subcategory1 loading with caching"""
    response = get_dropdown_data(
        model_class=ProductSubCategory1,
        name_field='product_sub_category',
        cache_key_prefix=f'subcat1_{category_id}',
        additional_filters={'category_id': category_id}
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'subcategories': [{'id': item['id'], 'name': item['product_sub_category']} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response

@require_GET
def ajax_subcat2(request, subcat1_id):
    """Optimized subcategory2 loading with caching"""
    response = get_dropdown_data(
        model_class=ProductSubCategory2,
        name_field='product_sub_category2',
        cache_key_prefix=f'subcat2_{subcat1_id}',
        additional_filters={'sub_category1_id': subcat1_id}
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'subcategories': [{'id': item['id'], 'name': item['product_sub_category2']} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response

@require_GET
def ajax_manufacturers(request):
    """Optimized manufacturers loading with caching"""
    response = get_dropdown_data(
        model_class=Manufacturer,
        name_field='manufacturer_name',
        cache_key_prefix='all_manufacturers'
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'manufacturers': [{'id': item['id'], 'name': item['manufacturer_name']} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response

@require_GET
def ajax_filter_products(request):
    """Optimized product filtering with prefetch_related and pagination"""
    category = request.GET.get('category')
    subcat1 = request.GET.get('subcat1')
    subcat2 = request.GET.get('subcat2')
    manufacturer = request.GET.get('manufacturer')
    keywords = request.GET.get('keywords')
    status_filter = request.GET.get('status', 'active')
    page = request.GET.get('page', 1)
    
    # Build optimized queryset
    queryset = Product.objects.select_related(
        'category', 'sub_category1', 'sub_category2', 'manufacturer'
    ).prefetch_related(
        Prefetch(
            'images',
            queryset=ProductImage.objects.filter(is_primary=True),
            to_attr='primary_images'
        )
    )
    
    # Apply status filter
    if status_filter == 'active':
        queryset = queryset.filter(status=True)
    elif status_filter == 'inactive':
        queryset = queryset.filter(status=False)
    # For 'all', no status filter is applied
    
    # Apply other filters
    if category:
        queryset = queryset.filter(category_id=category)
    if subcat1:
        queryset = queryset.filter(sub_category1_id=subcat1)
    if subcat2:
        queryset = queryset.filter(sub_category2_id=subcat2)
    if manufacturer:
        queryset = queryset.filter(manufacturer_id=manufacturer)
    if keywords:
        queryset = queryset.filter(
            Q(part_no__icontains=keywords) | Q(description__icontains=keywords)
        )
    
    # Order by id for consistent pagination
    queryset = queryset.order_by('id')
    
    # Pagination
    paginator = Paginator(queryset, 16)  # 16 items per page
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    # Optimize image loading for current page only
    products_with_images = []
    for product in page_obj:
        primary_image = product.primary_images[0] if product.primary_images else None
        products_with_images.append((product, primary_image))
    
    html = render_to_string(
        'product/_product_table_rows.html',
        {'products_with_images': products_with_images},
        request=request,
    )
    
    return JsonResponse({
        'html': html, 
        'count': len(products_with_images),
        'total_count': paginator.count,
        'paginator': {
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'page_range': list(paginator.page_range),
            'current_page': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        }
    })


@csrf_exempt
def save_quote_content(request, quote_id):
    """Save modified quote content to the database."""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            markdown_content = data.get('markdown_content')
            
            if markdown_content:
                # Here you could save the modified content to a new field in your model
                # For now, we'll just return success
                return JsonResponse({
                    'status': 'success',
                    'message': 'Quote content saved successfully!'
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No content provided'
                }, status=400)
                
        except (json.JSONDecodeError, KeyError) as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid data format: {str(e)}'
            }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

@require_GET
def ajax_all_categories(request):
    """Load all categories, subcategories, and manufacturers in a single request"""
    cache_key = 'all_category_data'
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        # Load all data with optimized queries
        categories = ProductCategory.objects.filter(status=True).order_by('product_category').values('id', 'product_category')
        
        # Get all subcategories with their relationships
        subcategories1 = ProductSubCategory1.objects.filter(status=True).select_related('category').order_by('product_sub_category').values(
            'id', 'product_sub_category', 'category_id'
        )
        subcategories2 = ProductSubCategory2.objects.filter(status=True).select_related('sub_category1').order_by('product_sub_category2').values(
            'id', 'product_sub_category2', 'sub_category1_id'
        )
        
        # Group subcategories by their parent
        subcat1_by_category = {}
        for subcat in subcategories1:
            category_id = subcat['category_id']
            if category_id not in subcat1_by_category:
                subcat1_by_category[category_id] = []
            subcat1_by_category[category_id].append({
                'id': subcat['id'],
                'name': subcat['product_sub_category']
            })
        
        subcat2_by_subcat1 = {}
        for subcat in subcategories2:
            subcat1_id = subcat['sub_category1_id']
            if subcat1_id not in subcat2_by_subcat1:
                subcat2_by_subcat1[subcat1_id] = []
            subcat2_by_subcat1[subcat1_id].append({
                'id': subcat['id'],
                'name': subcat['product_sub_category2']
            })
        
        # Load manufacturers
        manufacturers = Manufacturer.objects.filter(status=True).order_by('manufacturer_name').values('id', 'manufacturer_name')
        
        cached_data = {
            'categories': [{'id': c['id'], 'name': c['product_category']} for c in categories],
            'subcategories1_by_category': subcat1_by_category,
            'subcategories2_by_subcat1': subcat2_by_subcat1,
            'manufacturers': [{'id': m['id'], 'name': m['manufacturer_name']} for m in manufacturers]
        }
        
        # Cache for 1 hour
        cache.set(cache_key, cached_data, 3600)
    
    return JsonResponse(cached_data)

def optimized_product_list(request):
    """View for the optimized product list with performance monitoring"""
    return render(request, 'product/optimized_product_list.html', {
        'breadcrumbs': [
            {'name': 'Home', 'url': reverse('home'), 'position': 1, 'resolved': True},
            {'name': 'Product', 'url': reverse('product:product-list'), 'position': 2, 'resolved': True},
            {'name': 'Optimized Product List', 'url': None, 'position': 3, 'resolved': False},
        ]
    })

@login_required
@require_POST
def ajax_create_adhoc_for_quote(request, quote_id):
    """
    Create a one-time Ad-Hoc item and add it to this quote only.
    Ad-hoc items are not reusable catalog products.
    """
    from django.db import transaction

    quote = get_object_or_404(ProductQuote, id=quote_id)
    form = AdHocForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid quantity value'}, status=400)

    if quantity <= 0:
        return JsonResponse({'success': False, 'error': 'Quantity must be greater than 0'}, status=400)

    with transaction.atomic():
        adhoc = form.save(commit=False)
        adhoc.status = True
        adhoc.save()
        line_item = AdHocQuoteLine.objects.create(
            quote=quote,
            adhoc=adhoc,
            quantity=quantity,
            unit_price=adhoc.get_quote_unit_price(),
            adhoc_description=adhoc.description,
        )

    return JsonResponse({
        'success': True,
        'message': f'Added {quantity} of {adhoc.part_no} to quote',
        'line_item_id': line_item.id,
        'adhoc_id': adhoc.id,
        'part_no': adhoc.part_no,
        'description': adhoc.description,
        'quantity': quantity,
        'unit_price': str(line_item.unit_price),
        'total_price': str(line_item.total_price),
        'quote_subtotal': str(quote.subtotal),
    })


@login_required
@require_POST
def ajax_delete_adhoc_from_quote(request, quote_id, line_item_id):
    """Delete an Ad-Hoc line item from a quote and remove the one-time AdHoc row."""
    try:
        quote = get_object_or_404(ProductQuote, id=quote_id)
        line_item = get_object_or_404(AdHocQuoteLine, id=line_item_id, quote=quote)

        adhoc = line_item.adhoc
        adhoc_part_no = adhoc.part_no
        line_item.delete()
        if not AdHocQuoteLine.objects.filter(adhoc=adhoc).exists():
            adhoc.delete()

        return JsonResponse({
            'success': True,
            'message': f'Removed {adhoc_part_no} from quote',
            'quote_subtotal': str(quote.subtotal),
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def ajax_update_adhoc_quantity(request, line_item_id):
    """AJAX view to update quantity of an Ad-Hoc line item."""
    try:
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 1))

        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Quantity must be greater than 0'
            }, status=400)

        line_item = get_object_or_404(AdHocQuoteLine, id=line_item_id)
        line_item.quantity = quantity
        line_item.save()

        return JsonResponse({
            'success': True,
            'total_price': str(line_item.total_price),
            'quote_subtotal': str(line_item.quote.subtotal)
        })

    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'error': 'Invalid quantity value'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def update_line_item_price_type(request, line_item_id):
    """View to update the price type of a specific line item."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            price_type = data.get('price_type')
            
            if price_type not in ['retail_sell', 'builder_sell', 'surplus_sell']:
                return JsonResponse({'success': False, 'error': 'Invalid price type'})
            
            line_item = get_object_or_404(ProductQuoteLine, id=line_item_id)
            line_item.price_type = price_type
            line_item.save()  # This will recalculate the price and update the quote
            
            return JsonResponse({
                'success': True,
                'message': f'Price type updated to {price_type.replace("_", " ").title()}',
                'unit_price': float(line_item.unit_price),
                'total_price': float(line_item.total_price),
                'quote_subtotal': float(line_item.quote.subtotal)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def batch_update_products(request):
    """Batch update products page - Frontend only for now"""
    return render(request, 'product/batch_update.html')


# AJAX endpoints for batch update functionality
@login_required
@require_GET
def ajax_batch_update_manufacturers(request):
    """Get all manufacturers for batch update filters"""
    response = get_dropdown_data(
        model_class=Manufacturer,
        name_field='manufacturer_name',
        cache_key_prefix='batch_manufacturers'
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'success': True,
                'manufacturers': [{'id': item['id'], 'manufacturer_name': item['manufacturer_name']} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response


@login_required
@require_GET
def ajax_batch_update_categories(request):
    """Get all categories for batch update filters"""
    response = get_dropdown_data(
        model_class=ProductCategory,
        name_field='product_category',
        cache_key_prefix='batch_categories'
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'success': True,
                'categories': [{'id': item['id'], 'product_category': item['product_category']} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response


@login_required
@require_GET
def ajax_batch_update_subcategories1(request):
    """Get subcategories1 for batch update filters, optionally filtered by category"""
    category_id = request.GET.get('category_id')
    additional_filters = {'category_id': category_id} if category_id else None
    
    response = get_dropdown_data(
        model_class=ProductSubCategory1,
        name_field='product_sub_category',
        cache_key_prefix=f'batch_subcat1_{category_id or "all"}',
        additional_filters=additional_filters
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'success': True,
                'subcategories': [{'id': item['id'], 'product_sub_category': item['product_sub_category'], 'category_id': item.get('category_id')} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response


@login_required
@require_GET
def ajax_batch_update_subcategories2(request):
    """Get subcategories2 for batch update filters, optionally filtered by subcategory1"""
    subcategory1_id = request.GET.get('subcategory1_id')
    additional_filters = {'sub_category1_id': subcategory1_id} if subcategory1_id else None
    
    response = get_dropdown_data(
        model_class=ProductSubCategory2,
        name_field='product_sub_category2',
        cache_key_prefix=f'batch_subcat2_{subcategory1_id or "all"}',
        additional_filters=additional_filters
    )
    
    # Transform the response to match the expected format
    if response.status_code == 200:
        data = json.loads(response.content)
        if data['success']:
            transformed_data = {
                'success': True,
                'subcategories': [{'id': item['id'], 'product_sub_category2': item['product_sub_category2'], 'sub_category1_id': item.get('sub_category1_id')} for item in data['data']]
            }
            return JsonResponse(transformed_data)
    
    return response


@login_required
@require_GET
def ajax_batch_update_products(request):
    """Get filtered products for batch update with pagination"""
    try:
        # Get filter parameters
        manufacturer_id = request.GET.get('manufacturer_id')
        category_id = request.GET.get('category_id')
        subcategory1_id = request.GET.get('subcategory1_id')
        subcategory2_id = request.GET.get('subcategory2_id')
        status = request.GET.get('status')
        keywords = request.GET.get('keywords', '').strip()
        page = int(request.GET.get('page', 1))
        per_page = 16
        
        # Build queryset
        queryset = Product.objects.select_related(
            'manufacturer', 'category', 'sub_category1', 'sub_category2'
        ).all()
        
        # Apply filters
        if manufacturer_id:
            queryset = queryset.filter(manufacturer_id=manufacturer_id)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if subcategory1_id:
            queryset = queryset.filter(sub_category1_id=subcategory1_id)
        if subcategory2_id:
            queryset = queryset.filter(sub_category2_id=subcategory2_id)
        if status:
            queryset = queryset.filter(status=(status == 'active'))
        if keywords:
            queryset = queryset.filter(
                Q(part_no__icontains=keywords) |
                Q(description__icontains=keywords)
            )
        
        # Pagination
        paginator = Paginator(queryset, per_page)
        try:
            products_page = paginator.page(page)
        except (EmptyPage, PageNotAnInteger):
            products_page = paginator.page(1)
        
        # Serialize products
        products = []
        for product in products_page:
            products.append({
                'id': product.id,
                'part_no': product.part_no,
                'description': product.description,
                'manufacturer': product.manufacturer.manufacturer_name if product.manufacturer else None,
                'category': product.category.product_category if product.category else None,
                'sub_category1': product.sub_category1.product_sub_category if product.sub_category1 else None,
                'sub_category2': product.sub_category2.product_sub_category2 if product.sub_category2 else None,
                'status': 'active' if product.status else 'inactive',
                'retail_multiplier': float(product.retail_sell_multiplier) if product.retail_sell_multiplier else None,
                'builder_multiplier': float(product.builder_sell_multiplier) if product.builder_sell_multiplier else None,
                'surplus_multiplier': float(product.surplus_sell_multiplier) if product.surplus_sell_multiplier else None,
                'base_cost': float(product.unit_base_cost) if product.unit_base_cost else None,
                'material_cost': float(product.unit_material_cost) if product.unit_material_cost else None,
                'labor_cost': float(product.unit_labor_cost) if product.unit_labor_cost else None,
                'total_cost': float(product.unit_total_cost) if product.unit_total_cost else None,
                'builder_price': float(product.builder_sell) if product.builder_sell else None,
                'surplus_price': float(product.surplus_sell) if product.surplus_sell else None,
            })
        
        return JsonResponse({
            'success': True,
            'products': products,
            'pagination': {
                'current_page': products_page.number,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': products_page.has_next(),
                'has_previous': products_page.has_previous(),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def ajax_batch_update_apply(request):
    """Apply batch updates to selected products"""
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        updates = data.get('updates', {})
        
        if not product_ids:
            return JsonResponse({
                'success': False,
                'error': 'No products selected'
            }, status=400)
        
        if not updates:
            return JsonResponse({
                'success': False,
                'error': 'No updates specified'
            }, status=400)
        
        # Get products to update
        products = Product.objects.filter(id__in=product_ids)
        updated_count = 0
        
        for product in products:
            updated = False
            
            # Apply updates based on type
            for field, config in updates.items():
                if field == 'retail' and config['type'] == 'percentage-change':
                    if product.retail_sell_multiplier is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.retail_sell_multiplier * (Decimal('1') + (multiplier * percentage))
                        product.retail_sell_multiplier = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'builder' and config['type'] == 'percentage-change':
                    if product.builder_sell_multiplier is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.builder_sell_multiplier * (Decimal('1') + (multiplier * percentage))
                        product.builder_sell_multiplier = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'surplus' and config['type'] == 'percentage-change':
                    if product.surplus_sell_multiplier is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.surplus_sell_multiplier * (Decimal('1') + (multiplier * percentage))
                        product.surplus_sell_multiplier = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'base-cost' and config['type'] == 'percentage-change':
                    if product.unit_base_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.unit_base_cost * (Decimal('1') + (multiplier * percentage))
                        product.unit_base_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'material-cost' and config['type'] == 'percentage-change':
                    if product.unit_material_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.unit_material_cost * (Decimal('1') + (multiplier * percentage))
                        product.unit_material_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'labor-cost' and config['type'] == 'percentage-change':
                    if product.unit_labor_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.unit_labor_cost * (Decimal('1') + (multiplier * percentage))
                        product.unit_labor_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'total-cost' and config['type'] == 'percentage-change':
                    if product.unit_total_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.unit_total_cost * (Decimal('1') + (multiplier * percentage))
                        product.unit_total_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'builder-price' and config['type'] == 'percentage-change':
                    if product.builder_sell is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.builder_sell * (Decimal('1') + (multiplier * percentage))
                        product.builder_sell = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'surplus-price' and config['type'] == 'percentage-change':
                    if product.surplus_sell is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        percentage = Decimal(str(config['value'])) / Decimal('100')
                        new_value = product.surplus_sell * (Decimal('1') + (multiplier * percentage))
                        product.surplus_sell = max(Decimal('0'), new_value)
                        updated = True
                
                # Change By Value (absolute increase/decrease)
                elif field == 'retail' and config['type'] == 'change-by-value':
                    if product.retail_sell_multiplier is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.retail_sell_multiplier + (multiplier * Decimal(str(config['value'])))
                        product.retail_sell_multiplier = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'builder' and config['type'] == 'change-by-value':
                    if product.builder_sell_multiplier is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.builder_sell_multiplier + (multiplier * Decimal(str(config['value'])))
                        product.builder_sell_multiplier = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'surplus' and config['type'] == 'change-by-value':
                    if product.surplus_sell_multiplier is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.surplus_sell_multiplier + (multiplier * Decimal(str(config['value'])))
                        product.surplus_sell_multiplier = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'base-cost' and config['type'] == 'change-by-value':
                    if product.unit_base_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.unit_base_cost + (multiplier * Decimal(str(config['value'])))
                        product.unit_base_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'material-cost' and config['type'] == 'change-by-value':
                    if product.unit_material_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.unit_material_cost + (multiplier * Decimal(str(config['value'])))
                        product.unit_material_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'labor-cost' and config['type'] == 'change-by-value':
                    if product.unit_labor_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.unit_labor_cost + (multiplier * Decimal(str(config['value'])))
                        product.unit_labor_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'total-cost' and config['type'] == 'change-by-value':
                    if product.unit_total_cost is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.unit_total_cost + (multiplier * Decimal(str(config['value'])))
                        product.unit_total_cost = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'builder-price' and config['type'] == 'change-by-value':
                    if product.builder_sell is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.builder_sell + (multiplier * Decimal(str(config['value'])))
                        product.builder_sell = max(Decimal('0'), new_value)
                        updated = True
                elif field == 'surplus-price' and config['type'] == 'change-by-value':
                    if product.surplus_sell is not None:
                        multiplier = 1 if config['action'] == 'increase' else -1
                        new_value = product.surplus_sell + (multiplier * Decimal(str(config['value'])))
                        product.surplus_sell = max(Decimal('0'), new_value)
                        updated = True
                
                # Change To (set absolute value)
                elif field == 'retail' and config['type'] == 'change-to':
                    print(f"Setting retail multiplier to {config['value']}")
                    product.retail_sell_multiplier = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'builder' and config['type'] == 'change-to':
                    print(f"Setting builder multiplier to {config['value']}")
                    product.builder_sell_multiplier = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'surplus' and config['type'] == 'change-to':
                    print(f"Setting surplus multiplier to {config['value']}")
                    product.surplus_sell_multiplier = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'base-cost' and config['type'] == 'change-to':
                    product.unit_base_cost = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'material-cost' and config['type'] == 'change-to':
                    product.unit_material_cost = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'labor-cost' and config['type'] == 'change-to':
                    product.unit_labor_cost = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'total-cost' and config['type'] == 'change-to':
                    product.unit_total_cost = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'builder-price' and config['type'] == 'change-to':
                    product.builder_sell = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
                elif field == 'surplus-price' and config['type'] == 'change-to':
                    product.surplus_sell = max(Decimal('0'), Decimal(str(config['value'])))
                    updated = True
            
            if updated:
                product.save()
                updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully updated {updated_count} products',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)