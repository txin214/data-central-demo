from django.contrib import admin
from sitework.models import *

from import_export.admin import ImportExportModelAdmin
from import_export import resources

from import_export import widgets, fields, resources
from django.utils import timezone

from .resources import SiteworkSubCatResource


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


class SiteworkQuoteLineResource (resources.ModelResource):
    class Meta:
        model = SiteworkQuoteLine

class SiteworkQuoteLineAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkQuoteLineResource]        
    search_fields = ['workdesc']

admin.site.register(SiteworkQuoteLine,SiteworkQuoteLineAdmin)

class SiteworkQuoteResource (resources.ModelResource):
    class Meta:
        model = SiteworkQuote

class SiteworkQuoteAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkQuoteResource]        

admin.site.register(SiteworkQuote,SiteworkQuoteAdmin)




class SiteworkSubCatAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkSubCatResource]        
    search_fields = ['workdesc','group']
    list_filter = ["calckey", "orderby", "group", "siteworkcat__id"]
    
admin.site.register(SiteworkSubCat, SiteworkSubCatAdmin)

# 
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

class MarketResource (resources.ModelResource):
    class Meta:
        model = Market

class MarketAdmin(ImportExportModelAdmin):
    resource_classes = [MarketResource]        

admin.site.register(Market, MarketAdmin)

class SiteworkSubCatGroupResource (resources.ModelResource):
    class Meta:
        model = SiteworkSubCatGroup

class SiteworkSubCatGroupAdmin(ImportExportModelAdmin):
    resource_classes = [SiteworkSubCatGroupResource]
    list_filter = ["group"]

admin.site.register(SiteworkSubCatGroup, SiteworkSubCatGroupAdmin)
