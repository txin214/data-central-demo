from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('edit-profile/', views.edit_profile_view, name='edit_profile'),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('company-info/', views.company_info_view, name='company_info'),
    path('company-forms/', views.company_forms_view, name='company_forms'),
    path('product-info-forms/', views.product_info_forms_view, name='product_info_forms'),
    path('forms/<path:file_key>', views.forms_file_redirect, name='forms_file_redirect'),
    # AJAX endpoints
    path('ajax/job-functions/', views.ajax_job_functions, name='ajax_job_functions'),
    path('ajax/access-levels/', views.ajax_access_levels, name='ajax_access_levels'),
    path('ajax/filter-employees/', views.ajax_filter_employees, name='ajax_filter_employees'),
]
