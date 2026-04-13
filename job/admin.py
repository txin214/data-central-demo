from django.contrib import admin
from .models import Job, JobType, JobNotes, JobQuoteProductNotes, PurchaseOrder, PurchaseOrderItem, Team, Holiday, Store, Sale, ChangeOrder, PaymentType, AccountCategory, Payment


@admin.register(JobType)
class JobTypeAdmin(admin.ModelAdmin):
    """Admin for JobType model."""
    list_display = ('name', 'status')
    list_filter = ('status',)
    search_fields = ('name',)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    """Admin for Job model."""
    list_display = (
        'job_code', 
        'customer', 
        'active',
        'sold',
        'job_description',
        'jobtype',
        'soldby'
    )
    list_filter = ('active', 'sold', 'jobtype', 'storelocation')
    search_fields = ('job_code', 'customer__first_name', 'customer__last_name', 'job_description')
    readonly_fields = ('job_code',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('job_code', 'customer', 'job_description', 'active', 'sold', 'jobtype')
        }),
        ('Location', {
            'fields': ('storelocation', 'address', 'city', 'state', 'zip', 'county', 'township')
        }),
        ('Team Assignment', {
            'fields': ('soldby', 'coordinator', 'carpenter')
        }),
        ('Dates', {
            'fields': ('datesold', 'startdate', 'completDate', 'initalcontactdate', 'initialmeasuredate', 'actualstart', 'actualend')
        }),
        ('Financial', {
            'fields': ('saleamount', 'estdays')
        }),
        ('Installation Dates', {
            'fields': ('cabneededdate', 'topinstalldate', 'promised', 'estinstall')
        }),
        ('Quotes', {
            'fields': ('sitework_quote',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'customer', 'jobtype', 'storelocation', 'soldby', 'coordinator', 'carpenter', 'county', 'sitework_quote'
        )


@admin.register(JobNotes)
class JobNotesAdmin(admin.ModelAdmin):
    """Admin for JobNotes model."""
    list_display = ('job', 'note_date', 'assigned_to', 'completed', 'note_preview')
    list_filter = ('completed', 'note_date', 'assigned_to')
    search_fields = ('job__job_code', 'note', 'assigned_to__first_name', 'assigned_to__last_name')
    readonly_fields = ('note_date',)
    date_hierarchy = 'note_date'
    
    fieldsets = (
        ('Note Information', {
            'fields': ('job', 'note', 'note_date')
        }),
        ('Assignment & Follow-up', {
            'fields': ('assigned_to', 'follow_up', 'completed')
        }),
    )
    
    def note_preview(self, obj):
        """Show first 50 characters of note."""
        return obj.note[:50] + "..." if len(obj.note) > 50 else obj.note
    note_preview.short_description = 'Note Preview'
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'job', 'assigned_to'
        )


@admin.register(JobQuoteProductNotes)
class JobQuoteProductNotesAdmin(admin.ModelAdmin):
    """Admin for JobQuoteProductNotes model."""
    list_display = ('job', 'quote', 'product_info', 'note_preview', 'created_date', 'created_by')
    list_filter = ('created_date', 'created_by', 'job__active', 'job__sold')
    search_fields = ('job__job_code', 'quote__id', 'line_item__product__part_no', 'note')
    readonly_fields = ('created_date', 'modified_date')
    date_hierarchy = 'created_date'
    
    fieldsets = (
        ('Note Information', {
            'fields': ('job', 'quote', 'line_item', 'note')
        }),
        ('Metadata', {
            'fields': ('created_date', 'created_by', 'modified_date', 'modified_by')
        }),
    )
    
    def product_info(self, obj):
        """Show product information."""
        if obj.line_item and obj.line_item.product:
            return f"{obj.line_item.product.part_no} - {obj.line_item.product.description[:30]}..."
        return "Unknown Product"
    product_info.short_description = 'Product'
    
    def note_preview(self, obj):
        """Show first 50 characters of note."""
        return obj.note[:50] + "..." if len(obj.note) > 50 else obj.note
    note_preview.short_description = 'Note Preview'
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'job', 'quote', 'line_item__product', 'created_by', 'modified_by'
        )


class PurchaseOrderItemInline(admin.TabularInline):
    """Inline admin for PurchaseOrderItem."""
    model = PurchaseOrderItem
    extra = 1
    fields = ('part_number', 'description', 'ordered_date', 'quantity', 'confirmed', 'cost', 'note')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    """Admin for PurchaseOrder model."""
    list_display = ('po_number', 'job', 'vendor', 'location', 'status', 'arrive_by_date', 'created_at')
    list_filter = ('status', 'location', 'created_at', 'arrive_by_date')
    search_fields = ('po_number', 'job__job_code', 'vendor__name', 'ship_to')
    readonly_fields = ('po_number', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [PurchaseOrderItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('po_number', 'job', 'vendor', 'status')
        }),
        ('Location & Shipping', {
            'fields': ('location', 'ship_to', 'arrive_by_date')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'job', 'vendor', 'created_by'
        )


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    """Admin for PurchaseOrderItem model."""
    list_display = ('purchase_order', 'part_number', 'description', 'quantity', 'received_quantity', 'confirmed', 'cost', 'total_cost')
    list_filter = ('confirmed', 'ordered_date', 'purchase_order__status')
    search_fields = ('part_number', 'description', 'purchase_order__po_number')
    readonly_fields = ('created_at', 'updated_at', 'total_cost')
    
    fieldsets = (
        ('Item Information', {
            'fields': ('purchase_order', 'part_number', 'description', 'ordered_date')
        }),
        ('Ordering', {
            'fields': ('quantity', 'confirmed', 'cost', 'total_cost')
        }),
        ('Receiving', {
            'fields': ('received_quantity', 'sent_to_job_quantity')
        }),
        ('Storage & Notes', {
            'fields': ('parts_storage_location', 'note')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'purchase_order__job', 'purchase_order__vendor'
        )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'team_type', 'order_by', 'max_daily_limit', 'average_daily_limit')
    list_filter = ('status', 'team_type')
    search_fields = ('name',)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name', 'recurring', 'created_at')
    list_filter = ('recurring', 'date')
    search_fields = ('name',)
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Holiday Information', {
            'fields': ('date', 'name', 'recurring')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'status', 'city', 'state', 'phone')
    list_filter = ('status', 'state')
    search_fields = ('store_name', 'city', 'state', 'zipcode')
    
    fieldsets = (
        ('Store Information', {
            'fields': ('store_name', 'status')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'city', 'state', 'zipcode', 'phone')
        }),
    )


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """Admin for Sale model."""
    list_display = ('job_code', 'sales_person_name', 'sale_date', 'product_code', 'sale_amount', 'tax')
    list_filter = ('sale_date', 'tax')
    search_fields = ('job__job_code', 'job__customer__first_name', 'job__customer__last_name', 'job__soldby__first_name', 'job__soldby__last_name')
    readonly_fields = ('job_code', 'sales_person_name', 'total_contract_amount', 'created_at', 'updated_at')
    date_hierarchy = 'sale_date'
    
    fieldsets = (
        ('Job Information', {
            'fields': ('job', 'job_code', 'sales_person_name')
        }),
        ('Sale Details', {
            'fields': ('sale_date', 'sale_amount', 'product_code', 'tax')
        }),
        ('Description & Notes', {
            'fields': ('comment', 'notes',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'job', 'job__customer', 'job__soldby'
        )


@admin.register(ChangeOrder)
class ChangeOrderAdmin(admin.ModelAdmin):
    """Admin for ChangeOrder model."""
    list_display = ('job', 'description_preview', 'amount', 'order_date', 'created_by')
    list_filter = ('order_date', 'created_at')
    search_fields = ('job__job_code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'order_date'
    
    fieldsets = (
        ('Change Order Information', {
            'fields': ('job', 'description', 'amount', 'order_date')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def description_preview(self, obj):
        """Show first 50 characters of description."""
        return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description
    description_preview.short_description = 'Description'
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'job', 'job__customer', 'created_by'
        )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Only show sold jobs in the job dropdown."""
        if db_field.name == "job":
            kwargs["queryset"] = Job.objects.filter(sold=True).select_related('customer')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(PaymentType)
class PaymentTypeAdmin(admin.ModelAdmin):
    """Admin for PaymentType model."""
    list_display = ('id', 'description', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('description',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Payment Type Information', {
            'fields': ('description', 'status')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AccountCategory)
class AccountCategoryAdmin(admin.ModelAdmin):
    """Admin for AccountCategory model."""
    list_display = ('id', 'code', 'description', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Account Category Information', {
            'fields': ('code', 'description', 'status')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for Payment model."""
    list_display = ('job', 'date', 'account_category', 'amount', 'discount', 'by', 'created_at')
    list_filter = ('date', 'account_category', 'created_at')
    search_fields = ('job__job_code', 'comment', 'account_category__code', 'account_category__description')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('job', 'date', 'account_category', 'amount', 'discount', 'comment', 'by')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queries with select_related."""
        return super().get_queryset(request).select_related(
            'job', 'job__customer', 'account_category', 'by'
        )
