from import_export import resources
from django.utils import timezone


from .models import SiteworkSubCat

class SiteworkSubCatResource (resources.ModelResource):
   
    def before_import_row(self,row,**kwargs):
        print("before_import_row")
        print(row['lastmodifieddate'])
        row['lastmodifieddate']= timezone.now()
        print(row['lastmodifieddate'])
        print(row['editallowance'])
        if row['editallowance'] == 'True':
            row['editallowance'] = 1
        else:
            row['editallowance'] = 0
        return super().before_import_row(row,**kwargs)
    
    class Meta:
        model = SiteworkSubCat
    
