from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

@login_required
def dashboard_home(request):
    """Main system dashboard showing overview from all apps"""
    context = {
        'page_title': 'Dashboard',
    }
    context['now'] = timezone.now()
    # CRM stats
    try:
        from crm.models import Customer
        context['customer_count'] = Customer.objects.count()
    except:
        context['customer_count'] = 0

    # Sitework stats
    try:
        from sitework.models import SiteworkQuote
        context['quote_count'] = SiteworkQuote.objects.count()
    except:
        context['quote_count'] = 0

    # Product stats
    try:
        from product.models import Product,ProductQuote
        context['product_count'] = Product.objects.count()
        context['product_quote_count'] = ProductQuote.objects.count()
    except:
        context['product_count'] = 0
        context['product_quote_count']=0

    # Job stats
    try:
        from job.models import Job
        context['job_count'] = Job.objects.count()
    except:
        context['job_count'] = 0

    # Account stats
    try:
        from accounts.models import Account
        context['account_count'] = Account.objects.count()
    except:
        context['account_count'] = 0

    return render(request, 'dashboard/dashboard_home.html', context)

