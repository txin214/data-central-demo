from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from . import views
from .views import (
    EditProductImagesView, ProductThankYouView,
    ProductListView, ProductDetail2View,
    ProductDeleteView, CategoryView, ProductCreateView, ProductDuplicateUpdateView, ProductUpdateView2, view_product_images,
    ajax_categories, ajax_subcat1, ajax_subcat2, ajax_manufacturers, ajax_filter_products, save_quote_content, ajax_all_categories
)

app_name = 'product'

urlpatterns = [
    # ===== PRODUCT MANAGEMENT URLs =====
    # Thank you page after successful product operations
    path('thank_you/', ProductThankYouView.as_view(), name='thank_you'),
    
    # Product CRUD operations
    path('create_product/', ProductCreateView.as_view(), name='product-create'),  # Create new product
    path('list_product/', ProductListView.as_view(), name='product-list'),  # List all products
    path('optimized_list/', views.optimized_product_list, name='optimized-product-list'),  # Optimized product listing with better performance
    path('product_detail2/<uuid:pk>', ProductDetail2View.as_view(), name='product-detail2'),  # View product details
    path('product_update2/<uuid:pk>', ProductUpdateView2.as_view(), name='product-update2'),  # Update existing product
    path('product_duplicate/<uuid:pk>', ProductDuplicateUpdateView.as_view(), name='product-duplicate'),  # Duplicate existing product
    path('product_delete/<uuid:pk>', ProductDeleteView.as_view(), name='product-delete'),  # Delete product
    
    # Product image management
    path('product/edit-images/<uuid:pk>/', EditProductImagesView.as_view(), name='edit-product-images'),  # Edit product images
    path('product/<uuid:pk>/images/', view_product_images, name='view_product_images'),  # View product images
    
    # ===== CATEGORY MANAGEMENT URLs =====
    path('product-categories/', CategoryView.as_view(), name='product-category'),  # Manage product categories
    
    # AJAX category operations
    path('ajax/update-category/<int:pk>/', views.ajax_update_category, name='ajax-update-category'),  # Update category via AJAX
    path('ajax/update-subcategory1/<int:pk>/', views.ajax_update_subcategory1, name='ajax-update-subcategory1'),  # Update subcategory1 via AJAX
    path('ajax/update-subcategory2/<int:pk>/', views.ajax_update_subcategory2, name='ajax-update-subcategory2'),  # Update subcategory2 via AJAX
    path('ajax/update-color/<int:pk>/', views.ajax_update_color, name='ajax-update-color'),  # Update color via AJAX
    path('ajax/add-category/', views.ajax_add_category, name='ajax-add-category'),  # Add new category via AJAX
    path('ajax/add-subcategory1/', views.ajax_add_subcategory1, name='ajax-add-subcategory1'),  # Add new subcategory1 via AJAX
    path('ajax/add-subcategory2/', views.ajax_add_subcategory2, name='ajax-add-subcategory2'),  # Add new subcategory2 via AJAX
    path('ajax/add-color/', views.ajax_add_color, name='ajax-add-color'),  # Add new color via AJAX
    path('ajax/delete-category/<int:pk>/', views.ajax_delete_category, name='ajax-delete-category'),  # Delete category via AJAX
    path('ajax/delete-subcategory1/<int:pk>/', views.ajax_delete_subcategory1, name='ajax-delete-subcategory1'),  # Delete subcategory1 via AJAX
    path('ajax/delete-subcategory2/<int:pk>/', views.ajax_delete_subcategory2, name='ajax-delete-subcategory2'),  # Delete subcategory2 via AJAX
    path('ajax/delete-color/<int:pk>/', views.ajax_delete_color, name='ajax-delete-color'),  # Delete color via AJAX
    
    # ===== MANUFACTURER MANAGEMENT URLs =====
    path('manufacturers/', views.manufacturer_list, name='manufacturers'),  # List all manufacturers
    path('manufacturer/create/', views.create_manufacturer, name='create_manufacturer'),  # Create manufacturer
    path('manufacturer/<uuid:manufacturer_uuid>/', views.edit_manufacturer, name='edit_manufacturer'),  # Edit manufacturer
    path('ajax/delete-manufacturer/<uuid:pk>/', views.ajax_delete_manufacturer, name='ajax_delete_manufacturer'),  # Delete manufacturer via AJAX
    path('ajax/search-manufacturers/', views.ajax_search_manufacturers, name='ajax_search_manufacturers'),  # Search manufacturers via AJAX
    path('ajax/filter-manufacturers-by-status/', views.ajax_filter_manufacturers_by_status, name='ajax_filter_manufacturers_by_status'),  # Filter manufacturers by status via AJAX
    
    # ===== VENDOR MANAGEMENT URLs =====
    path('vendors/', views.vendor_list, name='vendors'),  # List all vendors
    path('vendor/create/', views.create_vendor, name='create_vendor'),  # Create vendor
    path('vendor/<uuid:vendor_uuid>/', views.edit_vendor, name='edit_vendor'),  # Edit vendor
    path('ajax/delete-vendor/<uuid:pk>/', views.ajax_delete_vendor, name='ajax_delete_vendor'),  # Delete vendor via AJAX
    path('ajax/search-vendors/', views.ajax_search_vendors, name='ajax_search_vendors'),  # Search vendors via AJAX
    path('ajax/filter-vendors-by-status/', views.ajax_filter_vendors_by_status, name='ajax_filter_vendors_by_status'),  # Filter vendors by status via AJAX
    
    # ===== COST POOL MANAGEMENT URLs =====
    path('costpools/', views.costpool_list, name='costpools'),  # List all cost pools
    path('costpool/create/', views.create_costpool, name='create_costpool'),  # Create cost pool
    path('costpool/<int:costpool_id>/', views.edit_costpool, name='edit_costpool'),  # Edit cost pool
    path('ajax/delete-costpool/<int:pk>/', views.ajax_delete_costpool, name='ajax_delete_costpool'),  # Delete cost pool via AJAX
    path('ajax/filter-costpools/', views.ajax_filter_costpools, name='ajax_filter_costpools'),  # Filter cost pools via AJAX
    path('ajax/costpool-manufacturers/', views.ajax_costpool_manufacturers, name='ajax_costpool_manufacturers'),  # Get manufacturers for cost pools
    path('ajax/costpool-categories/', views.ajax_costpool_categories, name='ajax_costpool_categories'),  # Get categories for cost pools
    path('ajax/costpool-subcat1/<int:category_id>/', views.ajax_costpool_subcat1, name='ajax_costpool_subcat1'),  # Get subcategory1 for cost pools
    path('ajax/costpool-subcat2/<int:subcat1_id>/', views.ajax_costpool_subcat2, name='ajax_costpool_subcat2'),  # Get subcategory2 for cost pools
    path('ajax/costpool-linked-products/<int:costpool_id>/', views.ajax_costpool_linked_products, name='ajax_costpool_linked_products'),  # Get linked products for cost pool
    path('ajax/update-costpool-products/<int:costpool_id>/', views.ajax_update_costpool_products, name='ajax_update_costpool_products'),  # Update selected products with cost pool multipliers
    
    # ===== BATCH UPDATE MANAGEMENT URLs =====
    path('batch-update/', views.batch_update_products, name='batch-update'),  # Batch update products page
    path('ajax/batch-update/manufacturers/', views.ajax_batch_update_manufacturers, name='ajax_batch_update_manufacturers'),  # Get manufacturers for batch update
    path('ajax/batch-update/categories/', views.ajax_batch_update_categories, name='ajax_batch_update_categories'),  # Get categories for batch update
    path('ajax/batch-update/subcategories1/', views.ajax_batch_update_subcategories1, name='ajax_batch_update_subcategories1'),  # Get subcategories1 for batch update
    path('ajax/batch-update/subcategories2/', views.ajax_batch_update_subcategories2, name='ajax_batch_update_subcategories2'),  # Get subcategories2 for batch update
    path('ajax/batch-update/products/', views.ajax_batch_update_products, name='ajax_batch_update_products'),  # Get filtered products for batch update
    path('ajax/batch-update/apply/', views.ajax_batch_update_apply, name='ajax_batch_update_apply'),  # Apply batch updates to products
    
    # ===== FINISH & LEAD TIME MANAGEMENT URLs =====
    path('finishes/', views.finish_list, name='finishes'),  # List all finishes
    path('finishes/edit/<int:finish_id>/', views.edit_finish, name='edit_finish'),  # Edit finish
    path('ajax/delete-finish/<int:pk>/', views.ajax_delete_finish, name='ajax_delete_finish'),  # Delete finish via AJAX
    path('ajax/search-finishes/', views.ajax_search_finishes, name='ajax_search_finishes'),  # Search finishes via AJAX
    path('lead-times/', views.lead_time_list, name='lead_time'),  # List lead times
    
    # ===== AJAX DATA LOADING URLs =====
    path('ajax/load-subcategories/', views.load_subcategories, name='ajax_load_subcategories'),  # Load subcategories dynamically
    path('ajax/load-related-products/', views.load_related_products, name='ajax_load_related_products'),  # Load related products
    path('ajax/vendors/', views.ajax_vendors, name='ajax_vendors'),  # Get vendors data via AJAX
    path('ajax/manufacturers/', views.ajax_manufacturers, name='ajax_manufacturers'),  # Get manufacturers data via AJAX
    path('ajax/categories/', ajax_categories, name='ajax-categories'),  # Get categories data via AJAX
    path('ajax/subcat1/<int:category_id>/', ajax_subcat1, name='ajax-subcat1'),  # Get subcategory1 data via AJAX
    path('ajax/subcat2/<int:subcat1_id>/', ajax_subcat2, name='ajax-subcat2'),  # Get subcategory2 data via AJAX
    path('ajax/filter/', ajax_filter_products, name='ajax-filter-products'),  # Filter products via AJAX
    path('ajax/all-categories/', ajax_all_categories, name='ajax-all-categories'),  # Get all categories via AJAX
    
    # ===== SMART SELECTS INTEGRATION =====
    path('chaining/', include('smart_selects.urls')),  # Chained dropdown functionality
    
    # ===== ACCESSORY & FINISH SEARCH URLs =====
    path('search_accessories/', views.search_accessories, name='search_accessories'),  # Search for accessories
    path('search_components/', views.search_components, name='search_components'),  # Search for components
    path('add_accessories/', views.add_accessories, name='add_accessories'),  # Add accessories to products
    path('remove_accessory/', views.remove_accessory, name='remove_accessory'),  # Remove accessories from products
    path('remove_component/', views.remove_component, name='remove_component'),  # Remove components from products
    path('add_components/', views.add_components, name='add_components'),  # Add components to products
    
    # ===== PRODUCT QUOTE MANAGEMENT URLs =====
    path('quotes/', views.product_quote_list, name='product_quote_list'),  # List all product quotes
    path('quotes/add/', views.add_product_quote, name='add_product_quote'),  # Create new product quote
    path('quotes/add/<int:job_id>/', views.add_product_quote, name='add_product_quote_for_job'),  # Create quote for specific job
    path('quotes/update/<int:quote_id>/', views.update_quote, name='quote_update'),  # Update existing quote
    path('quotes/delete/<int:quote_id>/', views.delete_quote, name='delete_quote'),  # Delete quote
    path('quote/<int:quote_id>', views.quote_products, name='quote_products'),  # View quote products
    
    # Quote product management
    path('quotes/<int:quote_id>/add-product/<uuid:product_id>/', views.add_product, name='add_product'),  # Add product to quote
    path('quotes/add-multiple-products/<int:quote_id>/', views.add_multiple_products, name='add_multiple_products'),  # Add multiple products to quote
    path('quotes/<int:quote_id>/delete-product/<int:line_item_id>/', views.delete_product, name='delete_product'),  # Delete product from quote
    path('quotes/edit-quantity/<int:line_item_id>/', views.edit_quantity, name='edit_quantity'),  # Edit product quantity in quote
    path('quotes/update-price-type/<int:line_item_id>/', views.update_line_item_price_type, name='update_line_item_price_type'),  # Update line item price type
    
    # Quote reporting and PDF generation
    path('quotes/report/<int:quote_id>/', views.product_quote_report, name='product_quote_report'),  # Generate quote report
    path('quotes/pdf/<int:quote_id>/', views.product_quote_pdf, name='product_quote_pdf'),  # Generate quote PDF
    path('quotes/save/<int:quote_id>/', save_quote_content, name='save_quote_content'),  # Save quote content
    
    # AJAX quote operations
    path('ajax/product-quotes/', views.ajax_product_quotes, name='ajax_product_quotes'),  # Get product quotes via AJAX
    
    # ===== ADHOC QUOTE LINE MANAGEMENT URLs =====
    path('ajax/create-adhoc/', views.ajax_create_adhoc, name='ajax-create-adhoc'),  # Create adhoc line item via AJAX
    path('quotes/<int:quote_id>/add-adhoc/', views.ajax_add_adhoc_to_quote, name='ajax-add-adhoc-to-quote'),  # Add adhoc item to quote
    path('quotes/<int:quote_id>/delete-adhoc/<int:line_item_id>/', views.ajax_delete_adhoc_from_quote, name='ajax-delete-adhoc-from-quote'),  # Delete adhoc item from quote
    path('quotes/edit-adhoc-quantity/<int:line_item_id>/', views.ajax_update_adhoc_quantity, name='ajax-update-adhoc-quantity'),  # Update adhoc item quantity
    path('adhoc/', views.adhoc_list, name='adhoc-list'),  # List all adhoc items
    path('adhoc/delete/<int:adhoc_id>/', views.delete_adhoc, name='delete-adhoc'),  # Delete adhoc item
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
