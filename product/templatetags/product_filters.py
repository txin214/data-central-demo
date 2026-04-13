from django import template
from decimal import Decimal
from django.db.models import Count

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        if value is None or arg is None:
            return 0
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def count_subcategories1(category):
    """Efficiently count subcategories1 for a category"""
    return category.productsubcategory1_set.filter(status=True).count()

@register.filter
def count_subcategories2(subcategory1):
    """Efficiently count subcategories2 for a subcategory1"""
    return subcategory1.productsubcategory2_set.filter(status=True).count()

@register.filter
def count_colors(subcategory2):
    """Efficiently count colors for a subcategory2"""
    return subcategory2.color_set.filter(status=True).count()

@register.filter
def get_subcategories1_for_category(category, subcategories1_list):
    """Get subcategories1 for a specific category from the optimized list"""
    return [s for s in subcategories1_list if s.category_id == category.id]

@register.filter
def get_subcategories2_for_subcategory1(subcategory1, subcategories2_list):
    """Get subcategories2 for a specific subcategory1 from the optimized list"""
    return [s for s in subcategories2_list if s.sub_category1_id == subcategory1.id]

@register.filter
def get_colors_for_subcategory2(subcategory2, colors_list):
    """Get colors for a specific subcategory2 from the optimized list"""
    return [c for c in colors_list if c.sub_category2_id == subcategory2.id] 