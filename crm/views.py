from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect, JsonResponse
from django.views.generic import TemplateView, CreateView, ListView, DetailView, UpdateView, DeleteView
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_POST
from .models import Customer, Referral, County
from .forms import CustomerForm
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

# Create your views here.

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'crm/home.html'

class ThankYouView(LoginRequiredMixin, TemplateView):
    template_name = 'crm/thank_you.html'

class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    success_url = reverse_lazy('crm:list_customer')
    
    def form_valid(self,form):
        form.save(commit=True)
        messages.success(self.request, f'Customer "{form.instance.first_name} {form.instance.last_name}" has been created successfully.')
        return super().form_valid(form)
        
class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    context_object_name = "customer_list"
    queryset = Customer.objects.order_by('last_name')

class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    
    def get_object(self, queryset=None):
        """Override to use uuid instead of pk"""
        uuid = self.kwargs.get('pk')
        return Customer.objects.get(uuid=uuid)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['referrals'] = Referral.objects.all()
        context['counties'] = County.objects.all()
        # Get jobs associated with this customer (newest first by ID)
        from job.models import Job
        jobs = Job.objects.filter(customer=self.object).order_by('-id')
        context['jobs'] = jobs
        # Check if job_id is passed in the URL parameters
        job_id = self.request.GET.get('job_id')
        if job_id:
            try:
                context['job'] = Job.objects.get(id=job_id)
            except Job.DoesNotExist:
                context['job'] = None
        else:
            context['job'] = None
            
        return context

class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    fields = "__all__"
    success_url = reverse_lazy('crm:list_customer')
    
    def get_object(self, queryset=None):
        """Override to use uuid instead of pk"""
        uuid = self.kwargs.get('pk')
        return Customer.objects.get(uuid=uuid)

class CustomerDeleteView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'crm/customer_confirm_delete.html'
    success_url = reverse_lazy('crm:list_customer')
    
    def get_object(self, queryset=None):
        """Override to use uuid instead of pk"""
        uuid = self.kwargs.get('pk')
        return Customer.objects.get(uuid=uuid)

    def form_valid(self, form):
        # Instead of deleting, set status to 'C' (Closed)
        form.instance.status_flag = 'C'
        messages.success(self.request, f'Customer \"{form.instance.first_name} {form.instance.last_name}\" has been marked as closed.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Close'
        context['message'] = f'Are you sure you want to close customer \"{self.object.first_name} {self.object.last_name}\"? The customer will be marked as closed but not deleted.'
        return context

@method_decorator(require_POST, name='dispatch')
@method_decorator(login_required, name='dispatch')
class CustomerAjaxDeleteView(View):
    def post(self, request, pk):
        try:
            customer = Customer.objects.get(uuid=pk)
            customer_name = f"{customer.first_name} {customer.last_name}"
            # Instead of deleting, set status to 'C' (Closed)
            customer.status_flag = 'C'
            customer.save()
            return JsonResponse({
                'success': True,
                'message': f'Customer "{customer_name}" has been marked as closed.'
            })
        except Customer.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Customer not found.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    

#class CustomerFormView(FormView):
#    form_class = CustomerForm
#    template_name = 'crm/customer.html'
#    success_url = reverse_lazy('crm:thank_you')
#    def form_valid(self,form):
        # if request.method == 'POST':
        #     form = CustomerForm(request.POST)
        #     if form.is_valid():
#        print(form.cleaned_data)
                ##form.save(commit=True)
        #         return HomeView(request)
        # else:
        #     form = CustomerForm()
#        return super().form_valid(form)
        ##return render(request,'crm/customer.html',context={'form':form})
