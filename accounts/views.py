from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q
from .forms import CustomUserCreationForm, CustomLoginForm
from .models import UserProfile, Role, UserRole


class CustomLoginView(LoginView):
    """Custom login view with better styling and redirect handling"""
    template_name = 'accounts/login.html'
    form_class = CustomLoginForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        # Check if there's a 'next' parameter in the URL (from @login_required redirect)
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        return reverse_lazy('home')


class CustomLogoutView(LogoutView):
    """Custom logout view"""
    next_page = reverse_lazy('home')
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests by redirecting to POST"""
        return self.post(request, *args, **kwargs)
    
    def dispatch(self, request, *args, **kwargs):
        """Handle logout without success message"""
        return super().dispatch(request, *args, **kwargs)


class RegisterView(CreateView):
    """User registration view"""
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('home')
    
    def form_valid(self, form):
        """Auto-login user after successful registration"""
        response = super().form_valid(form)
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password1')
        user = authenticate(username=username, password=password)
        if user:
            login(self.request, user)
            messages.success(self.request, f'Account created successfully! Welcome, {username}!')
        return response


@login_required
def profile_view(request):
    """User profile view - display only"""
    return render(request, 'accounts/profile.html', {
        'user': request.user
    })


@login_required
def edit_profile_view(request):
    """Edit profile view with form handling"""
    if request.method == 'POST':
        # Update user fields
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Update profile fields
        date_of_birth = request.POST.get('date_of_birth')
        profile.date_of_birth = date_of_birth if date_of_birth else None
        profile.gender = request.POST.get('gender', '')
        profile.pronoun = request.POST.get('pronoun', '')
        profile.location = request.POST.get('location', '')
        profile.timezone = request.POST.get('timezone', '')
        profile.save()
        
        messages.success(request, 'Your profile has been updated successfully!')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/edit_profile.html', {
        'user': request.user
    })


class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change view with better styling"""
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')
    
    def form_valid(self, form):
        """Add success message on password change"""
        messages.success(self.request, 'Your password has been successfully changed!')
        return super().form_valid(form)


@login_required
def product_info_forms_view(request):
    """Product Info Forms view - displays product forms and pricing information"""
    return render(request, 'accounts/product_info_forms.html')


@login_required
def company_forms_view(request):
    """Company Forms view - displays company forms"""
    return render(request, 'accounts/company_forms.html')


@login_required
def company_info_view(request):
    """Company Info view - displays employees grouped by role description"""
    # Get all active users with their roles
    users_with_roles = User.objects.filter(
        user_roles__is_active=True,
        is_active=True
    ).select_related().prefetch_related('user_roles__role', 'profile').distinct().order_by('first_name', 'last_name')
    
    # Group users by role description
    employees_by_role = {}
    
    for user in users_with_roles:
        # Get user's active roles
        user_roles = user.user_roles.filter(is_active=True).select_related('role')
        
        for user_role in user_roles:
            role = user_role.role
            role_description = role.get_type_display()  # This gives us the human-readable role type
            
            if role_description not in employees_by_role:
                employees_by_role[role_description] = []
            
            # Get user profile info
            try:
                profile = user.profile
                location = profile.location if profile.location else "No location"
                title = profile.title if profile.title else "No title"
                cellphone = profile.cellphone if profile.cellphone else "No phone"
                deskphone = profile.deskphone if profile.deskphone else "No phone"
            except UserProfile.DoesNotExist:
                location = "No location"
                title = "No title"
                cellphone = "No phone"
                deskphone = "No phone"
            
            employee_info = {
                'user': user,
                'role': role,
                'location': location,
                'title': title,
                'email': user.email if user.email else "No email",
                'cellphone': cellphone,
                'deskphone': deskphone
            }
            
            # Avoid duplicates if user has multiple roles
            if employee_info not in employees_by_role[role_description]:
                employees_by_role[role_description].append(employee_info)
    
    # Sort roles alphabetically
    sorted_roles = sorted(employees_by_role.keys())
    
    # Calculate statistics
    total_employees = sum(len(employees) for employees in employees_by_role.values())
    total_roles = len(employees_by_role)
    
    context = {
        'employees_by_role': employees_by_role,
        'sorted_roles': sorted_roles,
        'total_employees': total_employees,
        'total_roles': total_roles,
    }
    
    return render(request, 'accounts/company_info.html', context)


@require_GET
@login_required
def ajax_job_functions(request):
    """AJAX endpoint to get all job functions"""
    # Get unique job function types
    job_functions = Role.objects.filter(is_active=True).values('type').distinct()
    
    data = []
    seen = set()
    
    for item in job_functions:
        job_function = item['type']
        if job_function not in seen:
            seen.add(job_function)
            # Get the display name for the job function
            role = Role.objects.filter(type=job_function, is_active=True).first()
            if role:
                data.append({
                    'value': job_function,
                    'label': role.get_type_display()
                })
    
    # Sort by label for better UX
    data.sort(key=lambda x: x['label'])
    
    return JsonResponse({'job_functions': data})


@require_GET
@login_required
def ajax_access_levels(request):
    """AJAX endpoint to get all access levels"""
    # Get unique access level names
    access_levels = Role.objects.filter(is_active=True).values('name').distinct()
    
    data = []
    seen = set()
    
    for item in access_levels:
        access_level = item['name']
        if access_level not in seen:
            seen.add(access_level)
            # Get the display name for the access level
            role = Role.objects.filter(name=access_level, is_active=True).first()
            if role:
                data.append({
                    'value': access_level,
                    'label': f"{access_level} ({role.get_name_display()})"
                })
    
    # Sort by label for better UX
    data.sort(key=lambda x: x['label'])
    
    return JsonResponse({'access_levels': data})


@require_GET
@login_required
def ajax_filter_employees(request):
    """AJAX endpoint to filter employees"""
    job_function = request.GET.get('job_function')
    access_level = request.GET.get('access_level')
    keywords = request.GET.get('keywords', '')
    
    # Get all active users with their roles
    users_with_roles = User.objects.filter(
        user_roles__is_active=True,
        is_active=True
    ).select_related().prefetch_related('user_roles__role', 'profile').distinct()
    
    # Apply filters independently - users must match ALL selected filters
    # but job function and access level are checked separately
    if job_function:
        # Filter users who have ANY role with this job function type
        users_with_roles = users_with_roles.filter(user_roles__role__type=job_function, user_roles__is_active=True)
    
    if access_level:
        # Filter users who have ANY role with this access level
        users_with_roles = users_with_roles.filter(user_roles__role__name=access_level, user_roles__is_active=True)
    
    if keywords:
        users_with_roles = users_with_roles.filter(
            Q(first_name__icontains=keywords) | 
            Q(last_name__icontains=keywords) | 
            Q(email__icontains=keywords) |
            Q(username__icontains=keywords)
        )
    
    # Re-apply distinct and ordering after filters
    users_with_roles = users_with_roles.distinct().order_by('first_name', 'last_name')
    
    # Group users by role description
    employees_by_role = {}
    
    for user in users_with_roles:
        # Get user's active roles
        user_roles = user.user_roles.filter(is_active=True).select_related('role')
        
        for user_role in user_roles:
            role = user_role.role
            role_description = role.get_type_display()
            
            if role_description not in employees_by_role:
                employees_by_role[role_description] = []
            
            # Get user profile info
            try:
                profile = user.profile
                location = profile.location if profile.location else "No location"
                title = profile.title if profile.title else "No title"
                cellphone = profile.cellphone if profile.cellphone else "No phone"
                deskphone = profile.deskphone if profile.deskphone else "No phone"
            except UserProfile.DoesNotExist:
                location = "No location"
                title = "No title"
                cellphone = "No phone"
                deskphone = "No phone"
            
            employee_info = {
                'user': user,
                'role': role,
                'location': location,
                'title': title,
                'email': user.email if user.email else "No email",
                'cellphone': cellphone,
                'deskphone': deskphone
            }
            
            # Avoid duplicates if user has multiple roles
            if employee_info not in employees_by_role[role_description]:
                employees_by_role[role_description].append(employee_info)
    
    # Sort roles alphabetically
    sorted_roles = sorted(employees_by_role.keys())
    
    # Render the table rows
    html = ""
    for role_description in sorted_roles:
        for employee in employees_by_role[role_description]:
            # Format title and location
            title = employee['title'] if employee['title'] != "No title" else '-'
            location = employee['location'] if employee['location'] != "No location" else '-'
            
            html += f"""
            <tr>
                <td>{employee['user'].first_name or '-'}</td>
                <td>{employee['user'].last_name or '-'}</td>
                <td>{role_description}</td>
                <td>{employee['role'].get_name_display()}</td>
                <td>{title}</td>
                <td>{location}</td>
                <td>
                    {f'<a href="tel:{employee["deskphone"]}" class="text-decoration-none">{employee["deskphone"]}</a>' if employee['deskphone'] != "No phone" else '-'}
                </td>
                <td>
                    {f'<a href="tel:{employee["cellphone"]}" class="text-decoration-none">{employee["cellphone"]}</a>' if employee['cellphone'] != "No phone" else '-'}
                </td>
                <td>
                    {f'<a href="mailto:{employee["email"]}" class="text-decoration-none">{employee["email"]}</a>' if employee['email'] != "No email" else '-'}
                </td>
            </tr>
            """
    
    return JsonResponse({'html': html})