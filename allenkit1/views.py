from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from product.models import Product, Manufacturer, Vendor
from job.models import Job
from crm.models import Customer

# help us get to a home page at the URL root.
@login_required
def homeview(request):
    return redirect("/crm/")

@login_required
def search_view(request):
    """Global search view that searches across Products, Jobs, Customers, Manufacturers, and Vendors."""
    query = request.GET.get('q', '').strip()
    
    products = []
    jobs = []
    customers = []
    manufacturers = []
    vendors = []
    
    if query:
        # Search Products by part_no (prefix match)
        products = Product.objects.filter(
            Q(part_no__istartswith=query)
        ).select_related('category', 'manufacturer')[:20]
        
        # Search Jobs by job_code
        jobs = Job.objects.filter(
            Q(job_code__icontains=query)
        ).select_related('customer', 'jobtype')[:20]
        
        # Search Customers by first_name and last_name
        # Split query to handle full name searches
        query_parts = query.split()
        if len(query_parts) >= 2:
            # If multiple words, search for first name and last name separately
            # Try first word as first name, last word as last name
            customers = Customer.objects.filter(
                Q(first_name__icontains=query_parts[0]) & Q(last_name__icontains=query_parts[-1])
            ) | Customer.objects.filter(
                # Also try reversed (in case user types "lastname firstname")
                Q(first_name__icontains=query_parts[-1]) & Q(last_name__icontains=query_parts[0])
            ) | Customer.objects.filter(
                # Also search for full name in either field
                Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )
        else:
            # Single word search - check both first_name and last_name
            customers = Customer.objects.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )
        customers = customers.distinct()[:20]
        
        # Search Manufacturers by manufacturer_name (case-insensitive partial match)
        manufacturers = Manufacturer.objects.filter(
            Q(manufacturer_name__icontains=query)
        )[:20]
        
        # Search Vendors by vendor_name (case-insensitive partial match)
        vendors = Vendor.objects.filter(
            Q(vendor_name__icontains=query)
        )[:20]
    
    context = {
        'query': query,
        'products': products,
        'jobs': jobs,
        'customers': customers,
        'manufacturers': manufacturers,
        'vendors': vendors,
        'has_results': bool(products or jobs or customers or manufacturers or vendors),
    }
    
    return render(request, 'search_results.html', context)