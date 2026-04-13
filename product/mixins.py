from django.shortcuts import redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.urls import reverse
from .models import ProductImage


class ImageHandlingMixin:
    """
    Mixin to handle image processing for Product views.
    Extracts common image handling logic from ProductCreateView, 
    ProductDuplicateUpdateView, and ProductUpdateView2.
    """
    
    def handle_product_images(self, form, product):
        """
        Handle multiple images and primary image setting for a product.
        
        Args:
            form: The form instance with cleaned data
            product: The product instance to associate images with
        """
        # Handle multiple images
        images = self.request.FILES.getlist('images')
        if images:
            # Create ProductImage objects for each image
            for image in images:
                ProductImage.objects.create(product=product, image=image)
            
            # If no primary image is specified, set the first image as primary
            if not form.cleaned_data.get('primary_image') and images:
                first_image = ProductImage.objects.filter(product=product).first()
                if first_image:
                    first_image.is_primary = True
                    first_image.save()
        
        # Set primary image from form data
        primary_image_id = form.cleaned_data.get('primary_image')
        if primary_image_id:
            ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
            ProductImage.objects.filter(id=primary_image_id).update(is_primary=True)
    
    def form_valid(self, form):
        """
        Override form_valid to handle images after saving the product.
        """
        self.object = form.save()
        self.handle_product_images(form, self.object)
        return redirect(self.get_success_url())


class BreadcrumbMixin:
    """
    Mixin to standardize breadcrumb generation across views.
    """
    
    def get_breadcrumbs(self):
        """
        Get breadcrumbs for the current view.
        Override this method in subclasses to provide specific breadcrumbs.
        """
        return []
    
    def get_context_data(self, **kwargs):
        """
        Add breadcrumbs to context.
        """
        context = super().get_context_data(**kwargs)
        context['breadcrumbs'] = self.get_breadcrumbs()
        return context
    
    def get_home_breadcrumb(self):
        """Get the standard home breadcrumb."""
        return {'name': 'Home', 'url': reverse('home'), 'position': 1, 'resolved': True}
    
    def get_product_breadcrumb(self):
        """Get the standard product breadcrumb."""
        return {'name': 'Product', 'url': reverse('product:product-list'), 'position': 2, 'resolved': True}
    
    def get_product_list_breadcrumb(self):
        """Get the standard product list breadcrumb."""
        return {'name': 'Product List', 'url': reverse('product:product-list'), 'position': 3, 'resolved': True}


class AjaxCRUDMixin:
    """
    Generic mixin for AJAX CRUD operations.
    Provides common patterns for add, update, and delete operations.
    """
    
    @classmethod
    def ajax_add(cls, request, form_class, parent_field=None, parent_id=None):
        """
        Generic AJAX add operation.
        
        Args:
            request: HTTP request
            form_class: Form class to use
            parent_field: Optional parent field name (e.g., 'category_id')
            parent_id: Optional parent ID from request.POST
        """
        form = form_class(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            
            # Handle parent field if specified
            if parent_field and parent_id:
                setattr(instance, parent_field, parent_id)
            
            instance.save()
            
            # Return success response with instance data
            response_data = {
                'success': True, 
                'id': instance.id,
                'name': getattr(instance, cls.name_field, str(instance))
            }
            
            # Add parent field info if applicable
            if parent_field and parent_id:
                response_data[f'{parent_field}_id'] = parent_id
                
            return JsonResponse(response_data)
        
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    @classmethod
    def ajax_update(cls, request, model_class, pk, form_class):
        """
        Generic AJAX update operation.
        
        Args:
            request: HTTP request
            model_class: Model class to query
            pk: Primary key of instance to update
            form_class: Form class to use
        """
        try:
            instance = model_class.objects.get(pk=pk)
            form = form_class(request.POST, instance=instance)
            
            if form.is_valid():
                form.save()
                return JsonResponse({
                    'success': True, 
                    'id': instance.id,
                    'name': getattr(instance, cls.name_field, str(instance))
                })
            
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            
        except model_class.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'{model_class.__name__} not found'}, status=404)
    
    @classmethod
    def ajax_delete(cls, request, model_class, pk):
        """
        Generic AJAX delete operation.
        
        Args:
            request: HTTP request
            model_class: Model class to query
            pk: Primary key of instance to delete
        """
        try:
            instance = model_class.objects.get(pk=pk)
            instance.delete()
            return JsonResponse({'success': True})
            
        except model_class.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'{model_class.__name__} not found'}, status=404) 