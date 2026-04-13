from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import render

def role_permission_required(permission_codename):
    """
    Decorator to check if user has permission through their roles
    Users without roles get full permissions by default
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("You must be logged in to access this page.")
            
            # If user has no active roles, give them full permissions
            if not request.user.user_roles.filter(is_active=True).exists():
                return view_func(request, *args, **kwargs)
            
            # Check if user has permission through any of their active roles
            has_permission = request.user.user_roles.filter(
                is_active=True,
                role__role_permissions__permission__codename=permission_codename
            ).exists()
            
            if not has_permission:
                return HttpResponseForbidden("You don't have permission to access this page.")
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
