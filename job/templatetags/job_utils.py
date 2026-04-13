from django import template
from collections import defaultdict

register = template.Library()

@register.filter
def format_currency(value):
    """Format a number as currency"""
    if value is None:
        return "$0.00"
    return f"${value:.2f}"

@register.filter
def format_date(value, format_string="m/d/Y"):
    """Format a date with fallback to empty string"""
    if value:
        return value.strftime(format_string)
    return ""

@register.filter
def get_full_name(user):
    """Get full name of user with fallback"""
    if user:
        return user.get_full_name()
    return ""

@register.filter
def yes_no(value):
    """Convert boolean to Yes/No"""
    return "Yes" if value else "No"

@register.filter
def active_status(value):
    """Convert boolean to Active/Inactive"""
    return "Active" if value else "Inactive"

@register.filter
def get_item(mapping, key):
    """Dictionary (or mapping) lookup in templates: mapping|get_item:key"""
    try:
        return mapping.get(key)
    except Exception:
        return None