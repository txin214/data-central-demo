def update_page_numbers(content, page_count):
    """
    Update all PAGE_PLACEHOLDER instances with actual page numbers
    
    Args:
        content (str): HTML content with PAGE_PLACEHOLDER
        page_count (int): Total number of pages
        
    Returns:
        str: Updated content with page numbers
    """
    for page_num in range(1, page_count + 1):
        content = content.replace('PAGE_PLACEHOLDER', f'{page_num} / {page_count}', 1)
    return content


def format_currency(amount):
    """Format amount as currency string"""
    if amount is None:
        return "$0.00"
    return f"${amount:.2f}"


def group_line_items_by_category(line_items, adhoc_items):
    """
    Group line items by category for product quotes
    
    Args:
        line_items: QuerySet of regular product line items
        adhoc_items: QuerySet of ad-hoc line items
        
    Returns:
        list: List of category data dictionaries
    """
    from collections import defaultdict
    
    category_groups = defaultdict(list)
    
    # Add regular product line items
    for line_item in line_items:
        category_name = line_item.product.category.product_category if line_item.product.category else 'Uncategorized'
        category_groups[category_name].append(('product', line_item))
    
    # Add ad-hoc line items
    for adhoc_item in adhoc_items:
        category_name = adhoc_item.adhoc.category.product_category if adhoc_item.adhoc.category else 'Uncategorized'
        category_groups[category_name].append(('adhoc', adhoc_item))
    
    # Create categories data list
    categories_data = []
    for category_name, items in category_groups.items():
        category_subtotal = 0
        for item_type, item in items:
            if item.total_price is not None:
                category_subtotal += item.total_price
        
        categories_data.append({
            'name': category_name,
            'items': items,
            'subtotal': format_currency(category_subtotal)
        })
    
    return categories_data


def group_sitework_by_category(sitework_quote):
    """
    Group sitework line items by category
    
    Args:
        sitework_quote: SiteworkQuote object
        
    Returns:
        list: List of category data dictionaries
    """
    from collections import defaultdict
    from sitework.models import SiteworkQuoteLine
    
    # Calculate prices first using the same logic as PDF
    SiteworkQuoteLine.objects.calc_price(sitework_quote.id)
    
    category_groups = defaultdict(list)
    
    # Use prefetched siteworkquoteline_set if available, otherwise fall back to sql_quotes
    if hasattr(sitework_quote, '_prefetched_objects_cache') and 'sql_quotes' in sitework_quote._prefetched_objects_cache:
        line_items = sitework_quote._prefetched_objects_cache['sql_quotes']
    else:
        line_items = sitework_quote.sql_quotes.select_related('cat').all()
    
    for line_item in line_items:
        # Only include items with quantity greater than 0
        if line_item.quantity > 0:
            category_groups[line_item.cat.name if line_item.cat else 'Uncategorized'].append(line_item)
    
    # Create categories data list
    categories_data = []
    for category_name, items in category_groups.items():
        category_subtotal = 0.0
        formatted_items = []
        
        for item in items:
            price = float(SiteworkQuoteLine.objects.compute_line_price(item))

            category_subtotal += price
            
            unit_amount_str = format_currency(item.unitamount)
            price_str = format_currency(price)
            
            formatted_items.append({
                'workdesc': item.workdesc,
                'quantity': item.quantity,
                'unit_amount_str': unit_amount_str,
                'price_str': price_str
            })
        
        categories_data.append({
            'name': category_name,
            'items': formatted_items,
            'subtotal': format_currency(category_subtotal)
        })
    
    return categories_data


def calculate_product_quote_pages(categories_data, max_height_mm=120):
    """
    Calculate how many pages a product quote needs based on realistic content height
    
    Args:
        categories_data: List of category data dictionaries from group_line_items_by_category
        max_height_mm: Maximum height in mm before footer (A4 is 297mm, leaving ~57mm for header/footer/margins)
        
    Returns:
        int: Number of pages needed
    """
    total_height_mm = 0
    
    # Product Proposed header (only on first page): ~15mm (reduced)
    total_height_mm += 15
    
    for category in categories_data:
        # Category header with lines: ~12mm (reduced from 15mm)
        total_height_mm += 12
        
        # Each item row: use same realistic calculation as split function
        for item_type, item in category['items']:
            if item_type == 'product':
                desc_length = len(str(item.product.description or ''))
                part_no_length = len(str(item.product.part_no or ''))
            else:
                desc_length = len(str(item.adhoc.description or ''))
                part_no_length = len(str(item.adhoc.part_no or ''))
            
            # Use same realistic calculation as split function
            row_height = 6  # Base height (padding: 8px top+bottom = 4mm, content ~2mm)
            
            # Only add extra height for very long descriptions
            if desc_length > 100:  # Only for really long descriptions
                extra_lines = (desc_length - 100) // 80  # Conservative line wrapping
                row_height += extra_lines * 3  # 3mm per extra line
            
            total_height_mm += row_height
        
        # Category spacing: match split function
        total_height_mm += 2
    
    # Calculate pages needed with more realistic height
    pages_needed = max(1, int((total_height_mm + max_height_mm - 1) // max_height_mm))
    
    return pages_needed


def split_categories_for_pagination(categories_data, max_height_mm=120):
    """
    Simple and reliable pagination that fits as much content as possible per page
    without creating duplicate headers.
    
    Args:
        categories_data: List of category data dictionaries
        max_height_mm: Maximum height in mm before footer
        
    Returns:
        list: List of page data, where each page contains categories that fit
    """
    pages = []
    current_page = []
    current_page_height = 15  # Start with header height for first page
    
    for category in categories_data:
        # Calculate full category height (header + all items) - more realistic
        category_header_height = 8 + 4  # category header (8mm) + table header (4mm) = 12mm
        
        # Calculate all items height with more realistic estimation
        items_height = 0
        for item_type, item in category['items']:
            if item_type == 'product':
                desc_length = len(str(item.product.description or ''))
                part_no_length = len(str(item.product.part_no or ''))
            else:
                desc_length = len(str(item.adhoc.description or ''))
                part_no_length = len(str(item.adhoc.part_no or ''))
            
            # More realistic row height estimation based on actual CSS
            row_height = 6  # Base height (padding: 8px top+bottom = 4mm, content ~2mm)
            
            # Only add extra height for very long descriptions
            if desc_length > 100:  # Only for really long descriptions
                extra_lines = (desc_length - 100) // 80  # Conservative line wrapping
                row_height += extra_lines * 3  # 3mm per extra line
            
            items_height += row_height
        
        total_category_height = category_header_height + items_height
        
        # Simple decision: does entire category fit on current page?
        if current_page_height + total_category_height <= max_height_mm:
            # Yes - add it to current page
            current_page.append(category)
            current_page_height += total_category_height + 2  # Minimal spacing between categories
        else:
            # No - start new page with this category
            if current_page:
                pages.append(current_page)
            current_page = [category]
            current_page_height = 15 + total_category_height + 2  # Header + category + spacing
    
    # Add the last page if it has content
    if current_page:
        pages.append(current_page)
    
    return pages
