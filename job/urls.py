from django.urls import path
from . import views

app_name = 'job'

urlpatterns = [
    # Batch Entry
    path('batch-entry/receipts/', views.batch_entry_receipts, name='batch_entry_receipts'),
    path('batch-entry/sales/', views.batch_entry_sales, name='batch_entry_sales'),
    path('batch-entry/change-orders/', views.batch_entry_change_orders, name='batch_entry_change_orders'),

    # Sales
    path('sales/', views.sales_list, name='sales_list'),
    path('sales/pdf/', views.sales_orders_pdf, name='sales_orders_pdf'),

    # Sales
    path('<int:job_id>/sales/', views.job_sales, name='job_sales'),
    path('<int:job_id>/sales/create/', views.job_sale_create, name='job_sale_create'),
    path('<int:job_id>/sales/bulk-create/', views.job_sales_bulk_create, name='job_sales_bulk_create'),
    path('<int:job_id>/sales/<int:sale_id>/edit/', views.job_sale_edit, name='job_sale_edit'),
    path('<int:job_id>/sales/<int:sale_id>/delete/', views.job_sale_delete, name='job_sale_delete'),
    path('<int:job_id>/sales/<int:sale_id>/', views.job_sale_view, name='job_sale_view'),
    path('<int:job_id>/sales/invoice-pdf/', views.job_sales_invoice_pdf, name='job_sales_invoice_pdf'),
    
    # Change Orders
    path('<int:job_id>/change-orders/', views.job_change_orders, name='job_change_orders'),
    path('<int:job_id>/change-orders/create/', views.job_change_order_create, name='job_change_order_create'),
    path('<int:job_id>/change-orders/<int:change_order_id>/edit/', views.job_change_order_edit, name='job_change_order_edit'),
    path('<int:job_id>/change-orders/<int:change_order_id>/delete/', views.job_change_order_delete, name='job_change_order_delete'),
    path('<int:job_id>/change-orders/pdf/', views.job_change_orders_pdf, name='job_change_orders_pdf'),
    
    # Accounting
    path('<int:job_id>/accounting/', views.job_accounting, name='job_accounting'),
    
    # Payments
    path('<int:job_id>/payments/', views.job_payments, name='job_payments'),
    path('<int:job_id>/payments/create/', views.job_payment_create, name='job_payment_create'),
    path('<int:job_id>/payments/<int:payment_id>/edit/', views.job_payment_edit, name='job_payment_edit'),
    path('<int:job_id>/payments/<int:payment_id>/delete/', views.job_payment_delete, name='job_payment_delete'),
    path('<int:job_id>/payments/<int:payment_id>/lien-waiver-pdf/', views.job_payment_lien_waiver_pdf, name='job_payment_lien_waiver_pdf'),
    
    # Job CRUD operations
    path('', views.JobListView.as_view(), name='job_list'),
    path('create/', views.JobCreateView.as_view(), name='job_create'),
    path('<int:pk>/', views.JobDetailUpdateView.as_view(), name='job_detail'),
    path('<int:pk>/quotes/', views.JobQuotesView.as_view(), name='job_quotes'),
    path('<int:pk>/edit/', views.JobUpdateView.as_view(), name='job_update'),
    path('<int:pk>/delete/', views.job_delete, name='job_delete'),
    path('<int:job_id>/customer/', views.job_customer_detail, name='job_customer_detail'),
    
    # Product quote management
    path('<int:job_id>/add-product-quote/', views.add_product_quote_to_job, name='add_product_quote'),
    path('<int:job_id>/product-quote/create/', views.job_product_quote_create, name='job_product_quote_create'),
    path('<int:job_id>/product-quote/update/', views.job_product_quote_update, name='job_product_quote_update'),
    path('<int:job_id>/product-quote/update/<int:quote_id>/', views.job_product_quote_update, name='job_product_quote_update_specific'),
    path('<int:job_id>/remove-product-quote/<int:quote_id>/', views.remove_product_quote_from_job, name='remove_product_quote'),
    path('<int:job_id>/quote/<int:quote_id>/products/', views.job_quote_products, name='job_quote_products'),
    path('<int:job_id>/quote/<int:quote_id>/add-multiple-products/', views.add_multiple_products_to_job_quote, name='add_multiple_products_to_job_quote'),
    path('<int:job_id>/products/', views.job_products, name='job_products'),
    path('<int:job_id>/add-product-ajax/', views.add_product_to_job_ajax, name='add_product_to_job_ajax'),
    
    # AJAX endpoints
    path('autocomplete/', views.JobAutocompleteView.as_view(), name='job_autocomplete'),
    path('ajax/search/', views.ajax_search_jobs, name='ajax_search_jobs'),
    
    # Sitework quote management
    path('<int:job_id>/sitework/', views.job_sitework_view, name='job_sitework'),
    path('<int:job_id>/sitework/create/', views.job_sitework_create, name='job_sitework_create'),
    path('<int:job_id>/sitework/update/', views.job_sitework_update, name='job_sitework_update'),
    path('<int:job_id>/sitework/update/<int:quote_id>/', views.job_sitework_update, name='job_sitework_update_specific'),
    path('<int:job_id>/sitework/delete/', views.job_sitework_delete, name='job_sitework_delete'),
    path('<int:job_id>/sitework/<int:quote_id>/pdf-preview/', views.job_sitework_quote_pdf_preview, name='job_sitework_quote_pdf_preview'),
    # Carpenter progress
    path('<int:job_id>/sitework/carpenter/', views.job_sitework_carpenter, name='job_sitework_carpenter'),
    path('<int:job_id>/sitework/carpenter/set-progress/', views.job_set_sitework_line_progress, name='job_set_sitework_line_progress'),
    # Attachments
    path('<int:job_id>/attachments/', views.job_attachments, name='job_attachments'),
    path('<int:job_id>/attachments/<int:attachment_id>/open/', views.job_attachment_open, name='job_attachment_open'),
    path('<int:job_id>/attachments/<int:attachment_id>/download/', views.job_attachment_download, name='job_attachment_download'),
    path('<int:job_id>/attachments/<int:attachment_id>/delete/', views.job_attachment_delete, name='job_attachment_delete'),
    
    # Top Entry (frontend only)
    path('<int:job_id>/top-entry/', views.job_top_entry, name='job_top_entry'),
    path('<int:job_id>/top-entry/<int:top_id>/delete/', views.job_top_delete, name='job_top_delete'),
    path('<int:job_id>/top-entry/<int:top_id>/batch-shift/', views.job_top_batch_shift, name='job_top_batch_shift'),
    path('<int:job_id>/top-entry/event/create/', views.job_event_create, name='job_event_create'),
    
    # Job-specific sitework detail views
    path('<int:job_id>/sitework/detail/<int:cat>/', views.job_sitework_detail, name='job_sitework_detail'),
    path('<int:job_id>/sitework/qty-popup/<int:cat>/<int:subcat>/<int:quan>/', views.job_sitework_qty_popup, name='job_sitework_qty_popup'),
    path('<int:job_id>/sitework/qty-post/', views.job_sitework_qty_post, name='job_sitework_qty_post'),
    path('<int:job_id>/sitework/comment-popup/<int:subcat>/<str:comment>/', views.job_sitework_comment_popup, name='job_sitework_comment_popup'),
    path('<int:job_id>/sitework/comment-post/', views.job_sitework_comment_post, name='job_sitework_comment_post'),

    # Weather API
    path('<int:job_id>/weather/', views.get_weather_data, name='get_weather_data'),
    
    # Print/Preview
    path('<int:job_id>/print-preview/', views.job_print_preview, name='job_print_preview'),
    path('<int:job_id>/print-generate-pdf/', views.job_print_generate_pdf, name='job_print_generate_pdf'),
    
    # xhtml2pdf PDF Generation
    path('<int:job_id>/pdf-generate/', views.job_pdf_generate, name='job_pdf_generate'),
    
    # Gantt Chart
    path('<int:job_id>/gantt/', views.job_gantt_view, name='job_gantt'),
    path('<int:job_id>/gantt/data/', views.job_gantt_data, name='job_gantt_data'),
    
    # Top Entry slot edit
    path('<int:job_id>/top-entry/slot/<int:slot_id>/edit/', views.top_slot_edit, name='top_slot_edit'),

    # Master Scheduler (all jobs calendar)
    path('scheduler/', views.master_scheduler, name='master_scheduler'),
    
    # Job Notes
    path('<int:job_id>/notes/', views.job_notes, name='job_notes'),
    path('<int:job_id>/notes/create/', views.job_notes_create, name='job_notes_create'),
    path('<int:job_id>/notes/update/', views.job_notes_update, name='job_notes_update'),
    path('<int:job_id>/notes/update/<int:note_id>/', views.job_notes_update, name='job_notes_update_specific'),
    path('<int:job_id>/notes/view/<int:note_id>/', views.job_notes_view, name='job_notes_view'),
    path('<int:job_id>/notes/<int:note_id>/edit/', views.job_notes_edit, name='job_notes_edit'),
    path('<int:job_id>/notes/<int:note_id>/delete/', views.job_notes_delete, name='job_notes_delete'),
    
    # Primary Quote Management
    path('<int:job_id>/product-quote/<int:quote_id>/set-primary/', views.set_primary_product_quote, name='set_primary_product_quote'),
    path('<int:job_id>/sitework-quote/<int:quote_id>/set-primary/', views.set_primary_sitework_quote, name='set_primary_sitework_quote'),
    
    # Product Notes
    path('<int:job_id>/quote/<int:quote_id>/product/<int:line_item_id>/note/', views.add_product_note, name='add_product_note'),
    path('<int:job_id>/product-note/<int:note_id>/update/', views.update_product_note, name='update_product_note'),
    path('<int:job_id>/product-note/<int:note_id>/delete/', views.delete_product_note, name='delete_product_note'),
    
    # Product Management
    path('<int:job_id>/quote/<int:quote_id>/product/<int:line_item_id>/delete/', views.delete_product_from_quote, name='delete_product_from_quote'),
    
    # Purchase Order Management
    path('<int:job_id>/purchase-orders/', views.job_purchase_orders, name='job_purchase_orders'),
    path('<int:job_id>/purchase-orders/sync-from-primary-quote/', views.sync_pos_from_primary_quote, name='job_po_sync_from_primary_quote'),
    path('<int:job_id>/purchase-order/create/', views.job_purchase_order_create, name='job_purchase_order_create'),
    path('<int:job_id>/purchase-order/<int:po_id>/', views.job_purchase_order_detail, name='job_purchase_order_detail'),
    path('<int:job_id>/purchase-order/<int:po_id>/edit/', views.job_purchase_order_edit, name='job_purchase_order_edit'),
    path('<int:job_id>/purchase-order/<int:po_id>/delete/', views.job_purchase_order_delete, name='job_purchase_order_delete'),
    path('<int:job_id>/purchase-order/<int:po_id>/item/add/', views.job_purchase_order_item_add, name='job_purchase_order_item_add'),
    path('<int:job_id>/purchase-order/<int:po_id>/item/<int:item_id>/edit/', views.job_purchase_order_item_edit, name='job_purchase_order_item_edit'),
    path('<int:job_id>/purchase-order/<int:po_id>/item/<int:item_id>/delete/', views.job_purchase_order_item_delete, name='job_purchase_order_item_delete'),
    path('<int:job_id>/purchase-order/<int:po_id>/item/<int:item_id>/toggle-confirm/', views.job_purchase_order_item_toggle_confirm, name='job_purchase_order_item_toggle_confirm'),
    path('<int:job_id>/purchase-orders/export-confirmed/', views.job_purchase_orders_export_confirmed, name='job_purchase_orders_export_confirmed'),
    path('<int:job_id>/purchase-order/<int:po_id>/pdf/', views.job_purchase_order_pdf, name='job_purchase_order_pdf'),
    path('<int:job_id>/purchase-order/<int:po_id>/email-preview/', views.job_purchase_order_email_preview, name='job_purchase_order_email_preview'),
    path('<int:job_id>/purchase-order/<int:po_id>/email-send/', views.job_purchase_order_email_send, name='job_purchase_order_email_send'),
    
    # Vendor Management
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendor/create/', views.vendor_create, name='vendor_create'),
    path('vendor/<int:vendor_id>/edit/', views.vendor_edit, name='vendor_edit'),
    path('vendor/<int:vendor_id>/delete/', views.vendor_delete, name='vendor_delete'),
    
    # Master Scheduler
    path('teams/', views.team_list, name='team_list'),
    path('teams/create/', views.team_create, name='team_create'),
    path('teams/<int:team_id>/edit/', views.team_edit, name='team_edit'),
] 