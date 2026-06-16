from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from sitework.models import *

from import_export.admin import ImportExportModelAdmin
from import_export import resources

from import_export import widgets, fields, resources
from django.utils import timezone
from django.core.paginator import Paginator

from .resources import SiteworkSubCatResource
from .forms import SiteworkSubCatAdminForm


class TzDateTimeWidget(widgets.DateTimeWidget):
    def clean(self, value, row=None, *args, **kwargs):
        dt = super().clean(value, row, *args, **kwargs)
        if dt and timezone.is_naive(dt):
            # Make the naive datetime aware using the project's default TIME_ZONE
            # This assumes the incoming data is in the default TIME_ZONE
            return timezone.make_aware(dt, timezone.utc)
        return dt




class SiteworkSubCatImageResource (resources.ModelResource):
    class Meta:
        model = SiteworkSubCatImage

class SiteworkSubCatImageAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkSubCatImageResource]       
    fields = ('calckey','name','desc','image','doc')
    search_fields = ['desc','calckey']
    list_display = ('calckey','get_calckey2','name','image','doc')
    def get_calckey2(self,obj):
        s = SiteworkSubCat.objects.filter(calckey=obj.calckey).first()
        return f'{obj.calckey}: {s.workdesc}'

admin.site.register(SiteworkSubCatImage,SiteworkSubCatImageAdmin)
#

class SiteworkQuoteLineResource (resources.ModelResource):
    class Meta:
        model = SiteworkQuoteLine

class SiteworkQuoteLineAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkQuoteLineResource]        
    search_fields = ['workdesc']

admin.site.register(SiteworkQuoteLine,SiteworkQuoteLineAdmin)
#

class SiteworkQuoteResource (resources.ModelResource):
    class Meta:
        model = SiteworkQuote

class SiteworkQuoteAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkQuoteResource]        

admin.site.register(SiteworkQuote,SiteworkQuoteAdmin)
#

##
class SiteworkSubCatAdmin(ImportExportModelAdmin):
    """Custom admin for SiteworkSubCat with two-column layout similar to subcat_form.html"""
    resource_classes = [SiteworkSubCatResource]
    search_fields = ['workdesc', 'group', 'calckey']
    list_filter = ['siteworkcat', 'group', 'status']
    list_display = ['calckey', 'workdesc', 'quantitydesc', 'basecost', 'unitamount', 'group', 'orderby']
    ordering = ['siteworkcat', 'orderby', 'group']
    
    # Custom admin view template
    custom_view_template = 'admin/sitework/siteworksubcat/change_list.html'
    
    def changelist_view(self, request, extra_context=None):
        """Override default changelist with custom two-column layout"""
        # Build category list with item counts
        categories = []
        for cat in SiteworkCat.objects.order_by('orderby'):
            count = SiteworkSubCat.objects.filter(siteworkcat=cat).count()
            categories.append({
                'id': cat.id,
                'name': cat.name,
                'item_count': count
            })
        
        # Get current category filter from query params
        current_category = request.GET.get('category', '')
        
        # Base queryset
        queryset = SiteworkSubCat.objects.all().order_by('siteworkcat__orderby', 'orderby', 'group')
        
        # Apply category filter if specified
        if current_category:
            queryset = queryset.filter(siteworkcat_id=current_category)
        
        # Handle search
        search_term = request.GET.get('q', '')
        if search_term:
            queryset = queryset.filter(workdesc__icontains=search_term)
        
        # Pagination
        paginator = Paginator(queryset, 100)  # Show 100 items per page
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        # Build context
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
            'model_name': self.model._meta.model_name,
            'title': f'Select {self.model._meta.verbose_name} to change',
            'categories': categories,
            'current_category': current_category,
            'total_count': SiteworkSubCat.objects.count(),
            'result_count': paginator.count,
            'result_list': page_obj,
            'page_obj': page_obj,
            'paginator': paginator,
            'has_add_permission': self.has_add_permission(request),
            'cl': None,  # For template compatibility
            'is_paginated': paginator.num_pages > 1,
            'q': search_term,
        }
        
        if extra_context:
            context.update(extra_context)
        
        return render(request, self.custom_view_template, context)

# Register the admin
admin.site.register(SiteworkSubCat, SiteworkSubCatAdmin)
    

##

 
class SiteworkCatResource (resources.ModelResource):
    class Meta:
        model = SiteworkCat

class SiteworkCatAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkCatResource]        

admin.site.register(SiteworkCat, SiteworkCatAdmin)
#

class MarketCategoryResource (resources.ModelResource):
    class Meta:
        model = MarketCategory

class MarketCategoryAdmin(ImportExportModelAdmin):
    resource_classes = [MarketCategoryResource]        

admin.site.register(MarketCategory, MarketCategoryAdmin)
#

class MarketResource (resources.ModelResource):
    class Meta:
        model = Market

class MarketAdmin(ImportExportModelAdmin):
    resource_classes = [MarketResource]        

admin.site.register(Market, MarketAdmin)
#

class SiteworkSubCatGroupResource (resources.ModelResource):
    class Meta:
        model = SiteworkSubCatGroup

class SiteworkSubCatGroupAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkSubCatGroupResource]
    list_filter = ["group"]

admin.site.register(SiteworkSubCatGroup, SiteworkSubCatGroupAdmin)
#
