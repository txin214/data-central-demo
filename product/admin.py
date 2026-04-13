from django.contrib import admin

# Register your models here.
from .models import (
    Color, FaucetDrill, LeadTime, ProductCategory, ProductComponent, ProductQuote, ProductQuoteLine, ProductSubCategory1, 
    ProductSubCategory2, Vendor, Product, ProductAccessory, 
    Manufacturer, VendorProductCategory, Finish, ProductImage, AdHoc, AdHocQuoteLine, CostPool, ProductCode
)

# admin.site.register(FaucetDrill)
# admin.site.register(LeadTime)
# admin.site.register(ProductCategory)
# admin.site.register(ProductSubCategory1)
# admin.site.register(ProductSubCategory2)
# admin.site.register(Vendor)
# admin.site.register(Product)
# admin.site.register(ProductAccessory)
# admin.site.register(Manufacturer)
# admin.site.register(VendorProductCategory)
# admin.site.register(Finish)
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1  # Number of empty forms to display
    
@admin.register(ProductCode)
class ProductCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'description')
    search_fields = ('code', 'description')
    ordering = ('code',)

@admin.register(FaucetDrill)
class FaucetDrillAdmin(admin.ModelAdmin):
    list_display = ('description',)

@admin.register(LeadTime)
class LeadTimeAdmin(admin.ModelAdmin):
    list_display = ('description', 'status')

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('product_category', 'status')

@admin.register(ProductSubCategory1)
class ProductSubCategory1Admin(admin.ModelAdmin):
    list_display = ('product_sub_category', 'category', 'status')
    list_filter = ('category',)

@admin.register(ProductSubCategory2)
class ProductSubCategory2Admin(admin.ModelAdmin):
    list_display = ('product_sub_category2', 'sub_category1', 'status')
    list_filter = ('sub_category1',)
    
@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('color_name', 'sub_category2', 'status')
    list_filter = ('sub_category2',)
    
@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('vendor_no', 'vendor_name', 'city', 'state', 'status')    

class ProductAccessoryInline(admin.TabularInline):
    model = Product.accessories.through  # This specifies the intermediary table
    fk_name = 'product'  # Specify the ForeignKey to use
    extra = 1  # Number of empty forms to display
    verbose_name = "Product Accessory"
    verbose_name_plural = "Product Accessories"
    
class ProductComponentInline(admin.TabularInline):
    model = ProductComponent
    extra = 1  # Adjust the number of extra forms displayed
    fk_name = 'product'  # Specify the ForeignKey to the main Product model
    autocomplete_fields = ['component']  # Make the component field searchable

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'part_no', 'description', 'category', 'sub_category1', 
        'sub_category2', 'manufacturer', 'cost_pool', 'status', 'get_accessories',
        'get_components'
    )
    list_filter = (
        'category', 'sub_category1', 'sub_category2', 
        'manufacturer', 'cost_pool', 'status'
    )
    inlines = [ProductAccessoryInline, ProductComponentInline, ProductImageInline]  # Add the inline model admin
    autocomplete_fields = ['accessories', 'components', 'cost_pool']  # Make fields searchable
    search_fields = ['part_no', 'description', 'accessories__part_no', 'accessories__description',
                     'components__part_no', 'components__description', 'cost_pool__manufacturer__manufacturer_name']

    def get_accessories(self, obj):
        return ", ".join([str(accessory) for accessory in obj.accessories.all()])
    get_accessories.short_description = 'Accessories'
    
    def get_components(self, obj):
        return ", ".join([f"{component.component} (Qty: {component.component_qty})" for component in obj.product_components.all()])
    get_components.short_description = 'Components'
      
    def get_queryset(self, request):
        # Override get_queryset to ensure correct filtering
        qs = super().get_queryset(request)
        return qs.prefetch_related('accessories', 'product_components__component', 'cost_pool')
    
    actions = ['link_to_costpools', 'sync_multipliers', 'unlink_from_costpools']
    
    def link_to_costpools(self, request, queryset):
        """Link selected products to their matching cost pools"""
        linked_count = 0
        exact_matches = 0
        partial_matches = 0
        no_matches = 0
        
        for product in queryset:
            success, cost_pool, match_type = product.link_to_matching_cost_pool()
            if success:
                product.sync_multipliers_from_cost_pool()
                product.save()
                linked_count += 1
                if match_type == 'exact':
                    exact_matches += 1
                else:
                    partial_matches += 1
            else:
                no_matches += 1
        
        self.message_user(
            request,
            f'Linked {linked_count} products to cost pools. '
            f'Exact matches: {exact_matches}, Partial matches: {partial_matches}, '
            f'No matches: {no_matches}'
        )
    link_to_costpools.short_description = "Link to matching CostPools"
    
    def sync_multipliers(self, request, queryset):
        """Sync multipliers from linked cost pools"""
        synced_count = 0
        
        for product in queryset:
            if product.cost_pool and product.sync_multipliers_from_cost_pool():
                product.save()
                synced_count += 1
        
        self.message_user(
            request,
            f'Synced multipliers for {synced_count} products'
        )
    sync_multipliers.short_description = "Sync multipliers from CostPools"
    
    def unlink_from_costpools(self, request, queryset):
        """Remove cost pool links from selected products"""
        updated_count = queryset.update(cost_pool=None)
        self.message_user(
            request,
            f'Unlinked {updated_count} products from cost pools'
        )
    unlink_from_costpools.short_description = "Unlink from CostPools"


@admin.register(ProductAccessory)
class ProductAccessoryAdmin(admin.ModelAdmin):
    autocomplete_fields = ['product', 'accessory']  # Replace dropdowns with search bars
    search_fields = ['product__part_no', 'accessory__part_no']
    list_display = ('accessory',)

@admin.register(ProductComponent)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ('product', 'component', 'component_qty')
    search_fields = ('product__part_no', 'component__part_no')
    list_filter = ('product', 'component')
    autocomplete_fields = ['product', 'component']

@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ('manufacturer_name', 'city', 'state', 'status')
    search_fields = ['manufacturer_name']
    
@admin.register(VendorProductCategory)
class VendorProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'category')

@admin.register(Finish)
class FinishAdmin(admin.ModelAdmin):
    list_display = ('description', 'category', 'sub_category1', 'sub_category2', 'manufacturer', 'status')
    search_fields = ('description', 'comments')
    list_filter = ('category', 'sub_category1', 'sub_category2', 'manufacturer', 'status')
    search_help_text = "Search by finish description or comments."
    
class ProductQuoteLineInline(admin.TabularInline):
    """Inline admin for ProductQuoteLine."""
    model = ProductQuoteLine
    extra = 1  # Allows adding new lines directly
    readonly_fields = ('total_price',)  # Make total_price readonly
    fields = ('product', 'product_description', 'unit_price', 'quantity', 'total_price')

@admin.register(ProductQuote)
class ProductQuoteAdmin(admin.ModelAdmin):
    """Admin for ProductQuote."""
    list_display = ('id', 'name', 'customer', 'quoted_date', 'subtotal', 'status')
    list_filter = ('status', 'quoted_date')
    search_fields = ('name', 'customer__name', 'comments')
    readonly_fields = ('subtotal',)  # Subtotal is calculated
    inlines = [ProductQuoteLineInline]

@admin.register(ProductQuoteLine)
class ProductQuoteLineAdmin(admin.ModelAdmin):
    """Admin for ProductQuoteLine."""
    list_display = ('quote', 'product', 'product_description', 'quantity', 'unit_price', 'total_price')
    list_filter = ('quote', 'product')
    search_fields = ('product__part_no', 'product__description')

@admin.register(AdHoc)
class AdHocAdmin(admin.ModelAdmin):
    """Admin for AdHoc model."""
    list_display = ('part_no', 'description', 'category', 'retail_price', 'manufacturer', 'vendor', 'cost', 'status')
    list_filter = ('category', 'manufacturer', 'vendor', 'status')
    search_fields = ('part_no', 'description', 'category__product_category', 'manufacturer__manufacturer_name', 'vendor__vendor_name')
    readonly_fields = ('date_entered', 'date_updated')
    fieldsets = (
        ('Basic Information', {
            'fields': ('part_no', 'description', 'category')
        }),
        ('Pricing', {
            'fields': ('retail_price', 'cost')
        }),
        ('Relationships', {
            'fields': ('manufacturer', 'vendor')
        }),
        ('Status', {
            'fields': ('status', 'date_entered', 'date_updated')
        }),
    )

@admin.register(AdHocQuoteLine)
class AdHocQuoteLineAdmin(admin.ModelAdmin):
    """Admin for AdHocQuoteLine."""
    list_display = ('quote', 'adhoc', 'adhoc_description', 'quantity', 'unit_price', 'total_price')
    list_filter = ('quote', 'adhoc')
    search_fields = ('adhoc__part_no', 'adhoc__description')

@admin.register(CostPool)
class CostPoolAdmin(admin.ModelAdmin):
    """Admin for CostPool model."""
    list_display = ('manufacturer', 'category', 'sub_category1', 'sub_category2', 'retail', 'builder', 'surplus', 'status')
    list_filter = ('manufacturer', 'category', 'sub_category1', 'sub_category2', 'status')
    search_fields = ('manufacturer__manufacturer_name', 'category__product_category', 'sub_category1__product_sub_category', 'sub_category2__product_sub_category2')
    list_editable = ('retail', 'builder', 'surplus', 'status')
    
    fieldsets = (
        ('Manufacturer & Category', {
            'fields': ('manufacturer', 'category', 'sub_category1', 'sub_category2')
        }),
        ('Markup Rates', {
            'fields': ('retail', 'builder', 'surplus'),
            'description': 'Enter markup rates as decimals between 0.01 and 1.00 (e.g., 0.60 for 60% markup)'
        }),
        ('Status', {
            'fields': ('status',)
        }),
    )
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text for decimal fields
        form.base_fields['retail'].help_text = 'Retail markup (0.01 to 1.00)'
        form.base_fields['builder'].help_text = 'Builder markup (0.01 to 1.00)'
        form.base_fields['surplus'].help_text = 'Surplus markup (0.01 to 1.00)'
        return form