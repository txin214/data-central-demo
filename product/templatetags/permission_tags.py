from django import template
from django.contrib.auth.models import Permission

register = template.Library()

@register.filter
def has_role_permission(user, permission_codename):
    """Check if user has permission through their roles"""
    if not user or not user.is_authenticated:
        return False
    
    # If user has no active roles, give them full permissions
    if not user.user_roles.filter(is_active=True).exists():
        return True
    
    # Check if user has permission through any of their active roles
    return user.user_roles.filter(
        is_active=True,
        role__role_permissions__permission__codename=permission_codename
    ).exists()

@register.filter
def has_role(user, role_name):
    """Check if user has a specific role"""
    if not user or not user.is_authenticated:
        return False
    
    return user.user_roles.filter(role__name=role_name, is_active=True).exists()
