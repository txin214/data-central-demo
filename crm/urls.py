from django.urls import path

from . import views
from .views import (HomeView,ThankYouView,CustomerCreateView,
            CustomerListView,CustomerDetailView,CustomerUpdateView,CustomerDeleteView,CustomerAjaxDeleteView)

app_name = 'crm'

urlpatterns = [
    path('', HomeView.as_view(),name="home"),
    path('thank_you/', ThankYouView.as_view(),name="thank_you"),
    path('create_customer/',CustomerCreateView.as_view(),name='create_customer'),
    path('list_customer/',CustomerListView.as_view(),name='list_customer'),
    path('customer_detail/<uuid:pk>',CustomerDetailView.as_view(),name='detail_customer'),
    path('customer_update/<uuid:pk>',CustomerUpdateView.as_view(),name='update_customer'),
    path('customer_delete/<uuid:pk>',CustomerDeleteView.as_view(),name='delete_customer'),
    path('customer_delete/<uuid:pk>/',CustomerAjaxDeleteView.as_view(),name='ajax_delete_customer'),
]