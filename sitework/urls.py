# sitework/urls.py
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from . import views
from .views import (home_view,thankyou_view, qty_popup,comment_popup,basecost_popup,unitamount_popup,)

app_name = 'sitework'

urlpatterns = [
    # the left and right-hand stuff
    path("subcat_form/<int:cat>/<int:qte>/", views.subcat_form, name='subcat_form'), 

    path('home/', views.home_view,name="home"),
    #path('', views.home_view,name="home"),
    path('swthank_you/', views.thankyou_view,name="thank_you"),  
    # newer
    path('swshow/<int:qte>/', views.quote_show, name='show_url'),  
    path('swreport/<int:qte>/', views.report_show, name='show_report'),  
    path('swreport-simple/<int:qte>/', views.report_show_simple, name='show_report_simple'),  
    path("list/", views.quote_list, name='list_url'),  
    path('swcreate/', views.quote_create, name='create_url'),  
    path('delete/<int:quote_id>/', views.quote_delete, name='delete_url'),  

     # the form to edit a single sitework qty, right-hand
    path('qty_popup/<int:qte>/<int:cat>/<int:subcat>/<int:quan>/',views.qty_popup,name='qty_popup'),
    # save the value 
    path('qty_post/', views.qty_post, name='qty_post'),  

    # the form to edit a single sitework base cost, right-hand
    path('basecost_popup/<int:qte>/<int:cat>/<int:subcat>/<str:basecost>/',views.basecost_popup,name='basecost_popup'),
    # save the value 
    path('basecost_post/', views.basecost_post, name='basecost_post'),  

    # the form to edit a single sitework unit amount, right-hand
    path('unitamount_popup/<int:qte>/<int:cat>/<int:subcat>/<str:unitamt>/',views.unitamount_popup,name='unitamount_popup'),
    # save the value 
    path('unitamount_post/', views.unitamount_post, name='unitamount_post'),  
    
    # the form to edit a sitework comment, right-hand
    path('comment_popup/<int:qte>/<int:subcat>/<str:comment>/',views.comment_popup,name='comment_popup'),
    # save the value 
    path('comment_post/', views.comment_post, name='comment_post'),  

    # Celery task status endpoint for progress bar
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),

]
# + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


