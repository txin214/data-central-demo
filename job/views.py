from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from .utils import update_page_numbers, format_currency, group_line_items_by_category, group_sitework_by_category, calculate_product_quote_pages, split_categories_for_pagination
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponseRedirect, FileResponse, Http404
from django.views.decorators.http import require_POST, require_GET
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
import requests
import random
from urllib.parse import quote
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

import mimetypes
from .models import Job, JobType, JobNotes, JobQuoteProductNotes, SiteworkLineProgress, JobAttachment, PurchaseOrder, PurchaseOrderItem, Sale, ChangeOrder
from .forms import JobForm, JobCreateForm, JobProductQuoteForm, JobSearchForm, JobProductQuoteCreateForm, VendorForm, PurchaseOrderForm, PurchaseOrderItemForm, PurchaseOrderItemInlineFormSet
from product.models import Vendor, ProductQuote, ProductQuoteLine
from crm.models import Customer, StoreLocation, County, Referral
from sitework.models import SiteworkQuote, SiteworkQuoteLine, SiteworkCat, SiteworkSubCat
from sitework.forms import SiteworkQuoteForm, QtyForm
from django.http import HttpResponse
import json
import logging
from django.conf import settings
import os
import tempfile


@login_required
def team_list(request):
    """List all active teams (Master Scheduler > Team Builder)."""
    from .models import Team
    teams = Team.objects.all().order_by('order_by', 'name')
    return render(request, 'job/team_list.html', {
        'teams': teams,
    })


@login_required
def team_create(request):
    from .forms import TeamForm
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Team created successfully.')
            return redirect('job:team_list')
    else:
        form = TeamForm()
    return render(request, 'job/team_form.html', {'form': form, 'action': 'create'})


@login_required
def team_edit(request, team_id):
    from .forms import TeamForm
    from .models import Team
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, 'Team updated successfully.')
            return redirect('job:team_list')
    else:
        form = TeamForm(instance=team)
    return render(request, 'job/team_form.html', {'form': form, 'action': 'edit', 'team': team})

# -----------------------------
# Top Entry (frontend-only)
# -----------------------------
def job_top_entry(request, job_id):
    """Top Entry page: create and list job top entries; generate schedule slots."""
    job = get_object_or_404(Job, id=job_id)
    from .models import Team, JobTop, TopScheduleSlot

    if request.method == 'POST':
        room = request.POST.get('room') or ''
        top_type = request.POST.get('top_type') or ''
        notes = request.POST.get('notes', '')
        team_id = request.POST.get('team') or None
        fab = int(request.POST.get('fab', '0') or 0)
        inst = int(request.POST.get('inst', '0') or 0)
        template_date = request.POST.get('template_date') or None
        fabrication_date = request.POST.get('fabrication_date') or None
        install_date = request.POST.get('install_date') or None

        team = Team.objects.filter(id=team_id).first() if team_id else None

        # Validate date dependencies
        from datetime import datetime
        validation_errors = []
        
        # Parse dates if provided
        template_date_obj = None
        fabrication_date_obj = None
        install_date_obj = None
        
        try:
            if template_date:
                template_date_obj = datetime.strptime(template_date, '%Y-%m-%d').date()
        except ValueError:
            validation_errors.append('Invalid template date format.')
        
        try:
            if fabrication_date:
                fabrication_date_obj = datetime.strptime(fabrication_date, '%Y-%m-%d').date()
        except ValueError:
            validation_errors.append('Invalid fabrication date format.')
        
        try:
            if install_date:
                install_date_obj = datetime.strptime(install_date, '%Y-%m-%d').date()
        except ValueError:
            validation_errors.append('Invalid install date format.')
        
        # Helper functions for validation (using workday calculation)
        def get_next_workday_simple(start_date):
            """Return the next workday (Mon-Fri), skipping weekends and holidays."""
            from .models import Holiday
            from datetime import timedelta
            next_day = start_date + timedelta(days=1)
            max_iterations = 365
            iterations = 0
            while (next_day.weekday() >= 5 or Holiday.is_holiday(next_day)) and iterations < max_iterations:
                next_day = next_day + timedelta(days=1)
                iterations += 1
            return next_day
        
        def add_workdays_simple(start_date, num_days):
            """Add num_days workdays to start_date, skipping weekends and holidays."""
            if num_days <= 0:
                return start_date
            current_date = start_date
            days_added = 0
            max_iterations = 365 * 2
            iterations = 0
            while days_added < num_days and iterations < max_iterations:
                current_date = get_next_workday_simple(current_date)
                days_added += 1
                iterations += 1
            return current_date
        
        def calculate_end_date_from_hours_simple(start_date, hours):
            """Calculate end_date based on hours for validation."""
            if not hours or hours <= 8:
                return start_date
            extra_hrs = hours - 8
            additional_days = (extra_hrs + 7) // 8
            return add_workdays_simple(start_date, additional_days)
        
        # Check dependencies
        # Template must be before Fabrication
        if template_date_obj and fabrication_date_obj:
            if fabrication_date_obj <= template_date_obj:
                validation_errors.append('Fabrication date must be after Template date.')
            # Template has no hours, so end_date = start_date
            # Since we already checked fab > template, template_end < fab_start is automatically satisfied
        
        # Fabrication must be before Install
        if fabrication_date_obj and install_date_obj:
            if install_date_obj <= fabrication_date_obj:
                validation_errors.append('Install date must be after Fabrication date.')
            else:
                # Check that fab end_date (calculated from hours) doesn't overlap with install start
                fab_end = calculate_end_date_from_hours_simple(fabrication_date_obj, fab)
                if fab_end >= install_date_obj:
                    validation_errors.append(
                        f'Fabrication must finish before Install starts. '
                        f'With {fab} hours, Fabrication ends on {fab_end.strftime("%Y-%m-%d")}, but Install starts on {install_date_obj.strftime("%Y-%m-%d")}.'
                    )
        
        # Install must be after Template (redundant but ensures consistency)
        if template_date_obj and install_date_obj:
            if install_date_obj <= template_date_obj:
                validation_errors.append('Install date must be after Template date.')
        
        # If validation errors, show them and return
        if validation_errors:
            for error in validation_errors:
                messages.error(request, error)
            teams = Team.objects.all().order_by('order_by', 'name')
            tops = job.top_entries.select_related('team').order_by('display_order', 'id')
            return render(request, 'job/job_top_entry.html', {
                'job': job,
                'teams': teams,
                'tops': tops,
            })

        # Create JobTop
        jt = JobTop.objects.create(
            job=job,
            team=team,
            room=room,
            top_type=top_type,
            notes=notes,
            fab_count=fab,
            install_count=inst,
            template_date=template_date or None,
            fabrication_date=fabrication_date or None,
            install_date=install_date or None,
        )

        # Helper function to get next workday (skip weekends and holidays)
        def get_next_workday(start_date):
            """Return the next workday (Mon-Fri), skipping weekends and holidays."""
            from .models import Holiday
            from datetime import timedelta
            next_day = start_date + timedelta(days=1)
            # Skip weekends and holidays
            max_iterations = 365  # Safety limit to prevent infinite loops
            iterations = 0
            while (next_day.weekday() >= 5 or Holiday.is_holiday(next_day)) and iterations < max_iterations:
                next_day = next_day + timedelta(days=1)
                iterations += 1
            return next_day
        
        # Helper function to add N workdays to a date
        def add_workdays(start_date, num_days):
            """Add num_days workdays to start_date, skipping weekends and holidays."""
            if num_days <= 0:
                return start_date
            current_date = start_date
            days_added = 0
            max_iterations = 365 * 2  # Safety limit
            iterations = 0
            while days_added < num_days and iterations < max_iterations:
                current_date = get_next_workday(current_date)
                days_added += 1
                iterations += 1
            return current_date
        
        # Helper function to calculate end_date from hours
        def calculate_end_date_from_hours(start_date, hours):
            """Calculate end_date based on hours. Hours <= 8 = same day, hours > 8 = additional workdays."""
            if not hours or hours <= 8:
                return start_date
            # Calculate extra hours beyond 8
            extra_hrs = hours - 8
            # Calculate additional days needed (each day is 8 hours)
            # Use ceiling division: (extra_hrs + 7) // 8
            additional_days = (extra_hrs + 7) // 8
            # Add that many workdays to start_date
            return add_workdays(start_date, additional_days)
        
        # Generate schedule slots for the 3 canonical dates
        def add_slot(date_str, phase, hours=None):
            """Add a slot for a given date and phase. Calculate end_date based on hours."""
            if not date_str or not team:
                return
            try:
                from datetime import datetime
                d = datetime.strptime(date_str, '%Y-%m-%d').date()
            except Exception:
                return
            
            # Calculate end_date based on hours using proper calculation
            end_date = calculate_end_date_from_hours(d, hours)
            
            # Build concise phase tag shown inside [] plus team name
            phase_tag = {
                'template': 'temp',
                'fabrication': 'fab',
                'install': 'inst',
            }.get(phase, phase)
            note_value = f"{phase_tag} - {team.name}" if team and team.name else phase_tag

            TopScheduleSlot.objects.update_or_create(
                job=job,
                job_top=jt,
                phase=phase,
                defaults={
                    'team': team,
                    'start_date': d,
                    'end_date': end_date,
                    'label': f"{jt.room} – {jt.top_type}",
                    'note': note_value,
                }
            )

        add_slot(template_date, 'template')
        add_slot(fabrication_date, 'fabrication', hours=fab)
        add_slot(install_date, 'install', hours=inst)

        messages.success(request, 'Top entry created.')
        return redirect('job:job_top_entry', job_id=job.id)

    teams = Team.objects.all().order_by('order_by', 'name')
    tops = job.top_entries.select_related('team').order_by('display_order', 'id')

    # Get view mode (week or month) from query param, default to week
    view_mode = request.GET.get('view', 'week').strip()
    if view_mode not in ['week', 'month']:
        view_mode = 'week'

    # Import Holiday for workday checking
    from .models import Holiday
    
    # Calculate date range based on view mode
    from datetime import datetime, timedelta, date
    import calendar
    today = date.today()
    
    # First, determine the date range we'll need (view range + slot ranges)
    # We'll pre-fetch holidays for a wider range to cover all slots
    # Start with view range calculation
    if view_mode == 'month':
        month_param = request.GET.get('month')
        if month_param:
            try:
                month_start = datetime.strptime(month_param, '%Y-%m-%d').date()
                month_start = month_start.replace(day=1)
            except Exception:
                month_start = today.replace(day=1)
        else:
            month_start = today.replace(day=1)
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day)
        view_start_date = month_start
        view_end_date = month_end
    else:
        week_param = request.GET.get('week')
        if week_param:
            try:
                week_start = datetime.strptime(week_param, '%Y-%m-%d').date()
                week_start = week_start - timedelta(days=(week_start.weekday()))
            except Exception:
                week_start = today - timedelta(days=(today.weekday()))
        else:
            week_start = today - timedelta(days=(today.weekday()))
        view_start_date = week_start
        view_end_date = week_start + timedelta(days=6)
    
    # Expand range to include all slots (add 60 days buffer for slot ranges)
    holiday_range_start = view_start_date - timedelta(days=30)
    holiday_range_end = view_end_date + timedelta(days=30)
    
    # Pre-fetch all holidays from database for this range
    db_holidays = {}
    db_holidays_by_date = {}
    for h in Holiday.objects.filter(date__gte=holiday_range_start, date__lte=holiday_range_end):
        db_holidays_by_date[h.date] = h.name
    
    # Pre-fetch recurring holidays
    recurring_holidays = {}
    for h in Holiday.objects.filter(recurring=True):
        recurring_holidays[(h.date.month, h.date.day)] = h.name
    
    # Pre-compute US holidays using holidays library
    us_holidays_cache = {}
    try:
        import holidays
        us_holidays = holidays.UnitedStates()
        current_check = holiday_range_start
        while current_check <= holiday_range_end:
            holiday_name = us_holidays.get(current_check)
            display_name = Holiday.match_us_federal_holiday(holiday_name)
            if display_name:
                us_holidays_cache[current_check] = display_name
            current_check += timedelta(days=1)
    except ImportError:
        pass
    
    # Create cached holiday check functions
    def is_holiday_cached(check_date):
        """Check if a date is a holiday using cached data."""
        # Check US holidays cache
        if check_date in us_holidays_cache:
            return True
        # Check database holidays
        if check_date in db_holidays_by_date:
            return True
        # Check recurring holidays
        if (check_date.month, check_date.day) in recurring_holidays:
            return True
        return False
    
    def get_holiday_name_cached(check_date):
        """Get holiday name for a date using cached data."""
        # Check US holidays first
        if check_date in us_holidays_cache:
            return us_holidays_cache[check_date]
        # Check database holidays
        if check_date in db_holidays_by_date:
            return db_holidays_by_date[check_date]
        # Check recurring holidays
        if (check_date.month, check_date.day) in recurring_holidays:
            return recurring_holidays[(check_date.month, check_date.day)]
        return None
    
    # Helper function to check if a date is a workday (weekday and not a holiday)
    def is_workday(check_date):
        """Check if a date is a workday (Monday-Friday, not a holiday)."""
        # Check if it's a weekend (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            return False
        # Check if it's a holiday using cached function
        if is_holiday_cached(check_date):
            return False
        return True
    
    # Now generate display dates based on view mode (using already calculated view_start_date and view_end_date)
    if view_mode == 'month':
        # Generate all days in the month (including weekends and holidays)
        display_dates = []
        date_info = []  # List of dicts with date and holiday info
        current_date = view_start_date
        while current_date <= view_end_date:
            display_dates.append(current_date)
            holiday_name = get_holiday_name_cached(current_date)
            date_info.append({
                'date': current_date,
                'is_workday': is_workday(current_date),
                'is_weekend': current_date.weekday() >= 5,
                'is_holiday': holiday_name is not None,
                'holiday_name': holiday_name,
            })
            current_date += timedelta(days=1)
        
        # For context
        prev_view = (view_start_date - timedelta(days=1)).replace(day=1)
        if view_start_date.month == 12:
            next_view = date(view_start_date.year + 1, 1, 1)
        else:
            next_view = date(view_start_date.year, view_start_date.month + 1, 1)
    else:
        # Generate all days for the week (Monday-Sunday)
        display_dates = []
        date_info = []  # List of dicts with date and holiday info
        for i in range(7):
            d = view_start_date + timedelta(days=i)
            display_dates.append(d)
            holiday_name = get_holiday_name_cached(d)
            date_info.append({
                'date': d,
                'is_workday': is_workday(d),
                'is_weekend': d.weekday() >= 5,
                'is_holiday': holiday_name is not None,
                'holiday_name': holiday_name,
            })
        
        # For context
        prev_view = view_start_date - timedelta(days=7)
        next_view = view_start_date + timedelta(days=7)

    # Get event filter and team filter from query parameters
    event_filter = request.GET.get('filter', '').strip()
    team_filter = request.GET.get('team', '').strip()

    # Build schedule map: {team_id: {date: [labels]}}
    from collections import defaultdict
    schedule = defaultdict(lambda: defaultdict(list))
    # Filter slots that overlap with the view range
    # A slot overlaps if: (start_date <= view_end) AND (end_date >= view_start OR end_date is None)
    # This works for all event types: top, remodel, delivery
    slots_query = TopScheduleSlot.objects.select_related('team', 'job', 'job_top').filter(
        job=job,
    ).filter(
        # Slots with end_date that overlap the view range (start_date <= view_end AND end_date >= view_start)
        Q(end_date__isnull=False) & Q(start_date__lte=view_end_date) & Q(end_date__gte=view_start_date)
        |
        # Single-day slots (no end_date) that fall within the view range
        Q(end_date__isnull=True) & Q(start_date__gte=view_start_date) & Q(start_date__lte=view_end_date)
    )
    
    # Apply event type filter
    if event_filter == 'top':
        # Filter for top entries only (job_top is not null)
        slots_query = slots_query.filter(job_top__isnull=False)
    elif event_filter in ['remodel', 'delivery']:
        # Filter by event_type for standalone events
        slots_query = slots_query.filter(event_type=event_filter, job_top__isnull=True)
    
    # Apply team filter
    if team_filter:
        try:
            team_id = int(team_filter)
            slots_query = slots_query.filter(team_id=team_id)
        except (ValueError, TypeError):
            pass  # Invalid team filter, ignore it
    
    slots = slots_query
    phase_label = {'template': 'Template', 'fabrication': 'Fab', 'install': 'Install', 'extra': 'Extra'}
    assigned_team_ids = set()
    
    # Process all slots (top, remodel, delivery) and expand date ranges
    # This applies to all event types: slots with date ranges will appear on all days they cover
    for s in slots:
        # For standalone events (remodel/delivery), use event_type in the label
        if not s.job_top:
            inside = s.note or s.event_type.title()
        else:
            # For top entry slots, use note or phase
            inside = (s.note or phase_label.get(s.phase, s.phase))
        label = f"{s.job.job_code}[{inside}]"
        
        # Determine the date range for this slot (works for all event types)
        slot_start = s.start_date
        slot_end = s.end_date if s.end_date else s.start_date  # Use start_date as end_date if end_date is None
        
        # Generate all dates from slot_start to slot_end (inclusive)
        # This expands the slot to show on every day in its date range
        # Count all workdays in the slot range (even if outside displayed view)
        # Only display dates that are workdays AND within the displayed view
        current_date = slot_start
        day_number = 1  # Start counting from Day1 (workdays only)
        while current_date <= slot_end:
            # Check if it's a workday first
            if is_workday(current_date):
                # Only add dates that fall within the displayed view
                if view_start_date <= current_date <= view_end_date:
                    # Append day indicator to the label (Day1, Day2, etc.)
                    label_with_day = f"{label} - Day{day_number}"
                    schedule[s.team_id][current_date].append({'label': label_with_day, 'id': s.id, 'confirmed': s.confirmed})
                # Increment day counter for all workdays (even if outside displayed view)
                day_number += 1
            # Move to next date (but don't increment day_number for weekends/holidays)
            current_date += timedelta(days=1)
        
        assigned_team_ids.add(s.team_id)

    # Build rows for template
    # If team filter is active, only show that team; otherwise show all teams with slots
    if team_filter:
        try:
            team_id = int(team_filter)
            teams_for_schedule = [t for t in teams if t.id == team_id and t.id in assigned_team_ids]
        except (ValueError, TypeError):
            teams_for_schedule = [t for t in teams if t.id in assigned_team_ids]
    else:
        teams_for_schedule = [t for t in teams if t.id in assigned_team_ids]
    
    schedule_rows = []
    for t in teams_for_schedule:
        cells = []
        team_map = schedule.get(t.id, {})
        for i, d in enumerate(display_dates):
            cells.append({
                'items': team_map.get(d, []),
                'date_info': date_info[i] if i < len(date_info) else None
            })
        schedule_rows.append({'team': t, 'cells': cells})

    context = {
        'job': job,
        'teams': teams,
        'tops': tops,
        'display_dates': display_dates,
        'date_info': date_info,
        'view_mode': view_mode,
        'view_start_date': view_start_date,
        'view_end_date': view_end_date,
        'prev_view': prev_view,
        'next_view': next_view,
        'schedule_rows': schedule_rows,
        'event_filter': event_filter,
        'team_filter': team_filter,
    }
    return render(request, 'job/job_top_entry.html', context)


def job_top_delete(request, job_id, top_id):
    """Delete a top entry and its associated schedule slots."""
    job = get_object_or_404(Job, id=job_id)
    from .models import JobTop
    top = get_object_or_404(JobTop, id=top_id, job=job)
    
    if request.method == 'POST':
        # Delete the top entry (this will cascade delete associated TopScheduleSlot objects)
        top.delete()
        messages.success(request, 'Top entry deleted successfully.')
        # Redirect to current week
        from datetime import date, timedelta
        today = date.today()
        current_week_start = today - timedelta(days=(today.weekday()))
        return redirect('job:job_top_entry', job_id=job.id)
    
    # For GET requests, show a confirmation page or redirect
    return redirect('job:job_top_entry', job_id=job.id)


def job_top_batch_shift(request, job_id, top_id):
    """Batch shift slots for a top entry: move template+fab+install or just fab+install."""
    job = get_object_or_404(Job, id=job_id)
    from .models import JobTop, TopScheduleSlot, Holiday
    top = get_object_or_404(JobTop, id=top_id, job=job)
    next_url = request.GET.get('next') or reverse('job:job_top_entry', args=[job_id])
    
    if request.method == 'POST':
        shift_type = request.POST.get('shift_type', '').strip()  # 'all' or 'fab_install'
        days_str = request.POST.get('days', '').strip()
        
        try:
            days = int(days_str)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid number of days.')
            return redirect('job:job_top_entry', job_id=job.id)
        
        if days == 0:
            messages.info(request, 'No shift needed (0 days).')
            return redirect('job:job_top_entry', job_id=job.id)
        
        # Helper function to get next workday (skip weekends and holidays)
        def get_next_workday(start_date):
            """Return the next workday (Mon-Fri), skipping weekends and holidays."""
            from datetime import timedelta
            next_day = start_date + timedelta(days=1)
            max_iterations = 365
            iterations = 0
            while (next_day.weekday() >= 5 or Holiday.is_holiday(next_day)) and iterations < max_iterations:
                next_day = next_day + timedelta(days=1)
                iterations += 1
            return next_day
        
        # Helper function to subtract workdays (go backwards)
        def subtract_workdays(start_date, num_days):
            """Subtract num_days workdays from start_date, skipping weekends and holidays."""
            if num_days <= 0:
                return start_date
            current_date = start_date
            days_subtracted = 0
            max_iterations = 365 * 2
            iterations = 0
            from datetime import timedelta
            while days_subtracted < num_days and iterations < max_iterations:
                # Go back one calendar day
                current_date = current_date - timedelta(days=1)
                # If it's a workday, count it
                if current_date.weekday() < 5 and not Holiday.is_holiday(current_date):
                    days_subtracted += 1
                iterations += 1
            return current_date
        
        # Helper function to add N workdays to a date
        def add_workdays(start_date, num_days):
            """Add num_days workdays to start_date, skipping weekends and holidays."""
            if num_days <= 0:
                return start_date
            current_date = start_date
            days_added = 0
            max_iterations = 365 * 2
            iterations = 0
            while days_added < num_days and iterations < max_iterations:
                current_date = get_next_workday(current_date)
                days_added += 1
                iterations += 1
            return current_date
        
        # Get all slots for this top entry
        all_slots = TopScheduleSlot.objects.filter(job_top=top)
        
        # Determine which phases to shift
        phases_to_shift = []
        if shift_type == 'all':
            phases_to_shift = ['template', 'fabrication', 'install']
        elif shift_type == 'fab_install':
            phases_to_shift = ['fabrication', 'install']
        else:
            messages.error(request, 'Invalid shift type.')
            return redirect('job:job_top_entry', job_id=job.id)
        
        # Validate that advancing won't move dates before today
        from datetime import date
        today = date.today()
        validation_errors = []
        
        # Check all slots that will be shifted
        for slot in all_slots:
            if slot.phase in phases_to_shift:
                # Calculate what the new dates would be
                if days > 0:
                    new_start_date = add_workdays(slot.start_date, days)
                    new_end_date = add_workdays(slot.end_date if slot.end_date else slot.start_date, days)
                else:
                    new_start_date = subtract_workdays(slot.start_date, abs(days))
                    new_end_date = subtract_workdays(slot.end_date if slot.end_date else slot.start_date, abs(days))
                
                # Check if advancing would move dates before today
                if days < 0:  # Only check when advancing (negative days)
                    if new_start_date < today:
                        validation_errors.append(
                            f'{slot.phase.title()} phase would be moved to {new_start_date.strftime("%Y-%m-%d")}, which is before today ({today.strftime("%Y-%m-%d")}).'
                        )
                    if new_end_date and new_end_date < today:
                        validation_errors.append(
                            f'{slot.phase.title()} phase end date would be moved to {new_end_date.strftime("%Y-%m-%d")}, which is before today ({today.strftime("%Y-%m-%d")}).'
                        )
        
        # If validation errors, show them and don't proceed
        if validation_errors:
            for error in validation_errors:
                messages.error(request, error)
            return redirect(next_url)
        
        # Shift each slot
        slots_shifted = []
        for slot in all_slots:
            if slot.phase in phases_to_shift:
                # Shift start_date
                if days > 0:
                    new_start_date = add_workdays(slot.start_date, days)
                else:
                    new_start_date = subtract_workdays(slot.start_date, abs(days))
                
                slot.start_date = new_start_date
                
                # Shift end_date if it exists
                if slot.end_date:
                    if days > 0:
                        slot.end_date = add_workdays(slot.end_date, days)
                    else:
                        slot.end_date = subtract_workdays(slot.end_date, abs(days))
                else:
                    slot.end_date = new_start_date
                
                slot.save()
                slots_shifted.append(slot.phase)
        
        # Update JobTop dates to match slot start dates (re-query after save)
        template_slot = TopScheduleSlot.objects.filter(job_top=top, phase='template').first()
        fab_slot = TopScheduleSlot.objects.filter(job_top=top, phase='fabrication').first()
        install_slot = TopScheduleSlot.objects.filter(job_top=top, phase='install').first()
        
        if template_slot and 'template' in phases_to_shift:
            top.template_date = template_slot.start_date
        if fab_slot and 'fabrication' in phases_to_shift:
            top.fabrication_date = fab_slot.start_date
        if install_slot and 'install' in phases_to_shift:
            top.install_date = install_slot.start_date
        
        top.save()
        
        # Success message
        shift_direction = "forward" if days > 0 else "backward"
        phases_str = ", ".join([p.title() for p in phases_to_shift])
        messages.success(
            request, 
            f'Shifted {phases_str} by {abs(days)} workday(s) {shift_direction}.'
        )
        
        # Use next from POST if provided, otherwise use the one from GET
        redirect_url = request.POST.get('next') or next_url
        return redirect(redirect_url)
    
    # GET request - show the batch shift form
    return render(request, 'job/top_batch_shift.html', {
        'job': job,
        'top': top,
        'next': next_url,
    })


def job_event_create(request, job_id):
    """Create a standalone event (remodel/delivery) slot directly in the calendar."""
    job = get_object_or_404(Job, id=job_id)
    from .models import Team, TopScheduleSlot
    teams = Team.objects.all().order_by('order_by', 'name')
    
    if request.method == 'POST':
        event_type = request.POST.get('event_type', '').strip()
        team_id = request.POST.get('team', '').strip()
        start_date_str = request.POST.get('start_date', '').strip()
        end_date_str = request.POST.get('end_date', '').strip()
        note = request.POST.get('note', '').strip()
        hours = request.POST.get('hours', '').strip()
        
        if not event_type or not team_id or not start_date_str:
            messages.error(request, 'Event type, team, and start date are required.')
            return render(request, 'job/event_create.html', {
                'job': job,
                'teams': teams,
            })
        
        try:
            from datetime import datetime
            team = Team.objects.get(id=team_id)
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            
            # Parse end_date
            end_date = start_date
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            elif hours:
                # Calculate end_date based on hours (>8 extends to next workday)
                def get_next_workday(start_date):
                    from .models import Holiday
                    from datetime import timedelta
                    next_day = start_date + timedelta(days=1)
                    max_iterations = 365
                    iterations = 0
                    while (next_day.weekday() >= 5 or Holiday.is_holiday(next_day)) and iterations < max_iterations:
                        next_day = next_day + timedelta(days=1)
                        iterations += 1
                    return next_day
                
                try:
                    hrs = int(hours)
                    if hrs > 8:
                        end_date = get_next_workday(start_date)
                except ValueError:
                    pass
            
            # Determine phase based on event_type
            phase = 'extra'  # Default phase for standalone events
            
            # Create the slot
            slot = TopScheduleSlot.objects.create(
                job=job,
                job_top=None,  # Standalone events don't have job_top
                team=team,
                start_date=start_date,
                end_date=end_date,
                phase=phase,
                event_type=event_type,
                note=note or event_type.title(),
                label=f"{job.job_code} - {event_type.title()}",
                confirmed=False,
            )
            
            messages.success(request, f'{event_type.title()} event created successfully.')
            # Redirect to current week
            from datetime import date, timedelta
            today = date.today()
            current_week_start = today - timedelta(days=(today.weekday()))
            return redirect('job:job_top_entry', job_id=job.id)
        except Exception as e:
            messages.error(request, f'Error creating event: {str(e)}')
            return render(request, 'job/event_create.html', {
                'job': job,
                'teams': teams,
            })
    
    # For GET requests, render the form template
    return render(request, 'job/event_create.html', {
        'job': job,
        'teams': teams,
    })


def top_slot_edit(request, job_id, slot_id):
    job = get_object_or_404(Job, id=job_id)
    from .models import TopScheduleSlot, Team
    slot = get_object_or_404(TopScheduleSlot.objects.select_related('team', 'job', 'job_top'), id=slot_id, job=job)
    next_url = request.GET.get('next') or request.POST.get('next') or reverse('job:job_top_entry', args=[job_id])
    
    # Get all teams for dropdown
    teams = Team.objects.all().order_by('order_by', 'name')
    
    # Phase choices
    PHASE_CHOICES = [
        ('template', 'Template'),
        ('fabrication', 'Fabrication'),
        ('install', 'Install'),
        ('extra', 'Extra'),
    ]

    if request.method == 'POST':
        # Store original start_date for cascade calculation
        original_start_date = slot.start_date
        
        # Check if user wants to cascade shifts
        cascade_shifts = request.POST.get('cascade_shifts')
        
        # Update confirmed status
        slot.confirmed = bool(request.POST.get('confirmed'))
        
        # Update note
        note_val = request.POST.get('note', '').strip()
        if note_val:
            slot.note = note_val
        
        # Update team if provided
        team_id = request.POST.get('team')
        if team_id:
            try:
                new_team = Team.objects.get(id=team_id)
                slot.team = new_team
            except Team.DoesNotExist:
                pass
        
        # Update phase if provided
        phase_val = request.POST.get('phase')
        if phase_val and phase_val in [choice[0] for choice in PHASE_CHOICES]:
            slot.phase = phase_val
        
        # Update start_date
        new_start_date = None
        start_date_val = request.POST.get('start_date', '').strip()
        if start_date_val:
            try:
                from datetime import datetime
                new_start_date = datetime.strptime(start_date_val, '%Y-%m-%d').date()
                slot.start_date = new_start_date
            except ValueError:
                pass  # Keep existing start_date if invalid
        
        # Helper function to get next workday (skip weekends and holidays)
        def get_next_workday(start_date):
            """Return the next workday (Mon-Fri), skipping weekends and holidays."""
            from .models import Holiday
            from datetime import timedelta
            next_day = start_date + timedelta(days=1)
            # Skip weekends and holidays
            max_iterations = 365  # Safety limit to prevent infinite loops
            iterations = 0
            while (next_day.weekday() >= 5 or Holiday.is_holiday(next_day)) and iterations < max_iterations:
                next_day = next_day + timedelta(days=1)
                iterations += 1
            return next_day
        
        # Helper function to add N workdays to a date
        def add_workdays(start_date, num_days):
            """Add num_days workdays to start_date, skipping weekends and holidays."""
            if num_days <= 0:
                return start_date
            current_date = start_date
            days_added = 0
            max_iterations = 365 * 2  # Safety limit
            iterations = 0
            while days_added < num_days and iterations < max_iterations:
                current_date = get_next_workday(current_date)
                days_added += 1
                iterations += 1
            return current_date
        
        # Handle cascading date shifts if requested
        if cascade_shifts and new_start_date and original_start_date and slot.job_top:
            # Calculate the delta (in calendar days)
            delta_days = (new_start_date - original_start_date).days
            
            if delta_days != 0:
                # Determine which phases to cascade to
                downstream_phases = []
                if slot.phase == 'template':
                    downstream_phases = ['fabrication', 'install']
                elif slot.phase == 'fabrication':
                    downstream_phases = ['install']
                
                if downstream_phases:
                    # Get all slots for this job_top
                    downstream_slots = TopScheduleSlot.objects.filter(
                        job_top=slot.job_top,
                        phase__in=downstream_phases
                    )
                    
                    # Shift each downstream slot by the same delta
                    for downstream_slot in downstream_slots:
                        # Apply delta to start_date
                        if downstream_slot.start_date:
                            if delta_days > 0:
                                # Moving forward - add workdays
                                downstream_slot.start_date = add_workdays(downstream_slot.start_date, delta_days)
                            else:
                                # Moving backward - subtract workdays
                                # We need to go backwards, so we'll subtract calendar days and adjust for weekends/holidays
                                from datetime import timedelta
                                new_date = downstream_slot.start_date + timedelta(days=delta_days)
                                # Adjust if it lands on a weekend or holiday
                                while new_date.weekday() >= 5 or Holiday.is_holiday(new_date):
                                    new_date = new_date - timedelta(days=1)
                                downstream_slot.start_date = new_date
                        
                        # Apply delta to end_date if it exists
                        if downstream_slot.end_date:
                            if delta_days > 0:
                                downstream_slot.end_date = add_workdays(downstream_slot.end_date, delta_days)
                            else:
                                from datetime import timedelta
                                new_date = downstream_slot.end_date + timedelta(days=delta_days)
                                while new_date.weekday() >= 5 or Holiday.is_holiday(new_date):
                                    new_date = new_date - timedelta(days=1)
                                downstream_slot.end_date = new_date
                        
                        # Sync JobTop dates for downstream slots too
                        if downstream_slot.phase == 'template':
                            slot.job_top.template_date = downstream_slot.start_date
                        elif downstream_slot.phase == 'fabrication':
                            slot.job_top.fabrication_date = downstream_slot.start_date
                        elif downstream_slot.phase == 'install':
                            slot.job_top.install_date = downstream_slot.start_date
                        
                        downstream_slot.save()
                    
                    # Save JobTop with updated dates
                    slot.job_top.save()
                    
                    # Add success message
                    phase_names = ', '.join([p.title() for p in downstream_phases])
                    messages.success(request, f'Also shifted {phase_names} by {abs(delta_days)} days.')
        
        # Helper function to calculate end_date from hours
        def calculate_end_date_from_hours(start_date, hours):
            """Calculate end_date based on hours. Hours <= 8 = same day, hours > 8 = additional workdays."""
            if not hours or hours <= 8:
                return start_date
            # Calculate extra hours beyond 8
            extra_hrs = hours - 8
            # Calculate additional days needed (each day is 8 hours)
            # Use ceiling division: (extra_hrs + 7) // 8
            additional_days = (extra_hrs + 7) // 8
            # Add that many workdays to start_date
            return add_workdays(start_date, additional_days)
        
        # Handle Fab hours for fabrication phase
        recalculated_end_date = False
        validation_errors = []
        
        if slot.phase == 'fabrication':
            fab_hrs_val = request.POST.get('fab_hrs', '').strip()
            if fab_hrs_val:
                try:
                    fab_hrs = int(fab_hrs_val)
                    if fab_hrs < 0:
                        validation_errors.append('Fab hours cannot be negative.')
                    else:
                        slot.job_top.fab_count = fab_hrs
                        slot.job_top.save()
                        # Always recalculate end_date based on hours
                        slot.end_date = calculate_end_date_from_hours(slot.start_date, fab_hrs)
                        recalculated_end_date = True
                except ValueError:
                    validation_errors.append('Invalid fab hours value.')
        
        # Handle Inst hours for install phase
        elif slot.phase == 'install':
            inst_hrs_val = request.POST.get('inst_hrs', '').strip()
            if inst_hrs_val:
                try:
                    inst_hrs = int(inst_hrs_val)
                    if inst_hrs < 0:
                        validation_errors.append('Install hours cannot be negative.')
                    else:
                        slot.job_top.install_count = inst_hrs
                        slot.job_top.save()
                        # Always recalculate end_date based on hours
                        slot.end_date = calculate_end_date_from_hours(slot.start_date, inst_hrs)
                        recalculated_end_date = True
                except ValueError:
                    validation_errors.append('Invalid install hours value.')
        
        # Update end_date if manually provided (only if hours were NOT provided)
        # If hours were provided, end_date is already calculated above
        if not recalculated_end_date:
            end_date_val = request.POST.get('end_date', '').strip()
            if end_date_val:
                try:
                    from datetime import datetime
                    manual_end_date = datetime.strptime(end_date_val, '%Y-%m-%d').date()
                    
                    # Validate that manual end_date matches the hours if they exist
                    if slot.phase == 'fabrication' and slot.job_top:
                        expected_end_date = calculate_end_date_from_hours(slot.start_date, slot.job_top.fab_count)
                        if manual_end_date != expected_end_date:
                            validation_errors.append(
                                f'End date does not match fab hours ({slot.job_top.fab_count} hrs). '
                                f'Expected: {expected_end_date.strftime("%Y-%m-%d")}, but got: {manual_end_date.strftime("%Y-%m-%d")}. '
                                f'Update fab hours or let the system calculate end date automatically.'
                            )
                        else:
                            slot.end_date = manual_end_date
                    elif slot.phase == 'install' and slot.job_top:
                        expected_end_date = calculate_end_date_from_hours(slot.start_date, slot.job_top.install_count)
                        if manual_end_date != expected_end_date:
                            validation_errors.append(
                                f'End date does not match install hours ({slot.job_top.install_count} hrs). '
                                f'Expected: {expected_end_date.strftime("%Y-%m-%d")}, but got: {manual_end_date.strftime("%Y-%m-%d")}. '
                                f'Update install hours or let the system calculate end date automatically.'
                            )
                        else:
                            slot.end_date = manual_end_date
                    else:
                        # For other phases or no job_top, allow manual end_date
                        slot.end_date = manual_end_date
                except ValueError:
                    validation_errors.append('Invalid end date format.')
                    slot.end_date = slot.start_date
            else:
                # No end_date provided and no hours to calculate from
                # For fabrication/install phases, calculate from existing hours
                if slot.phase == 'fabrication' and slot.job_top:
                    slot.end_date = calculate_end_date_from_hours(slot.start_date, slot.job_top.fab_count)
                elif slot.phase == 'install' and slot.job_top:
                    slot.end_date = calculate_end_date_from_hours(slot.start_date, slot.job_top.install_count)
                else:
                    slot.end_date = slot.start_date
        
        # Validate date dependencies if this slot is part of a job_top
        if slot.job_top:
            # Get all slots for this job_top
            all_slots = TopScheduleSlot.objects.filter(job_top=slot.job_top)
            
            # Build dicts of phase -> start_date and end_date for validation
            phase_start_dates = {}
            phase_end_dates = {}
            for s in all_slots:
                if s.id == slot.id:
                    # Use the updated values for the current slot
                    phase_start_dates[slot.phase] = slot.start_date
                    phase_end_dates[slot.phase] = slot.end_date if slot.end_date else slot.start_date
                else:
                    phase_start_dates[s.phase] = s.start_date
                    phase_end_dates[s.phase] = s.end_date if s.end_date else s.start_date
            
            # Validate dependencies: Template must be before Fabrication
            if 'template' in phase_start_dates and 'fabrication' in phase_start_dates:
                # Template end_date must be before Fabrication start_date
                if phase_end_dates['template'] >= phase_start_dates['fabrication']:
                    validation_errors.append(
                        f'Template must finish before Fabrication starts. '
                        f'Template ends: {phase_end_dates["template"]}, Fabrication starts: {phase_start_dates["fabrication"]}'
                    )
            
            # Validate dependencies: Fabrication must be before Install
            if 'fabrication' in phase_start_dates and 'install' in phase_start_dates:
                # Fabrication end_date must be before Install start_date
                if phase_end_dates['fabrication'] >= phase_start_dates['install']:
                    validation_errors.append(
                        f'Fabrication must finish before Install starts. '
                        f'Fabrication ends: {phase_end_dates["fabrication"]}, Install starts: {phase_start_dates["install"]}'
                    )
            
            # Also validate start dates for clarity (redundant but helpful)
            if 'template' in phase_start_dates and 'fabrication' in phase_start_dates:
                if phase_start_dates['fabrication'] <= phase_start_dates['template']:
                    validation_errors.append('Fabrication start date must be after Template start date.')
            
            if 'fabrication' in phase_start_dates and 'install' in phase_start_dates:
                if phase_start_dates['install'] <= phase_start_dates['fabrication']:
                    validation_errors.append('Install start date must be after Fabrication start date.')
            
            # If validation fails, show error and don't save
            if validation_errors:
                for error in validation_errors:
                    messages.error(request, error)
                # Set default value for end_date if not set
                if not slot.end_date:
                    slot.end_date = slot.start_date
                return render(request, 'job/top_slot_edit.html', {
                    'job': job,
                    'slot': slot,
                    'teams': teams,
                    'phase_choices': PHASE_CHOICES,
                    'next': next_url,
                })
        
        # Sync JobTop dates with slot start_date to keep them consistent
        if slot.job_top:
            if slot.phase == 'template':
                slot.job_top.template_date = slot.start_date
            elif slot.phase == 'fabrication':
                slot.job_top.fabrication_date = slot.start_date
            elif slot.phase == 'install':
                slot.job_top.install_date = slot.start_date
            slot.job_top.save()
        
        slot.save()
        messages.success(request, 'Slot updated.')
        return redirect(next_url)

    # Set default value for end_date if not set
    if not slot.end_date:
        slot.end_date = slot.start_date
    
    return render(request, 'job/top_slot_edit.html', {
        'job': job,
        'slot': slot,
        'teams': teams,
        'phase_choices': PHASE_CHOICES,
        'next': next_url,
    })


@login_required
def master_scheduler(request):
    from .models import Team, TopScheduleSlot
    teams = Team.objects.all().order_by('order_by', 'name')

    # Import Holiday for workday checking
    from .models import Holiday
    
    # Get view mode (week or month) from query param, default to week
    view_mode = request.GET.get('view', 'week').strip()
    if view_mode not in ['week', 'month']:
        view_mode = 'week'

    # Calculate date range based on view mode
    from datetime import datetime, timedelta, date
    import calendar
    today = date.today()
    
    # First, determine the date range we'll need (view range + slot ranges)
    # We'll pre-fetch holidays for a wider range to cover all slots
    # Start with view range calculation
    if view_mode == 'month':
        month_param = request.GET.get('month')
        if month_param:
            try:
                month_start = datetime.strptime(month_param, '%Y-%m-%d').date()
                month_start = month_start.replace(day=1)
            except Exception:
                month_start = today.replace(day=1)
        else:
            month_start = today.replace(day=1)
        last_day = calendar.monthrange(month_start.year, month_start.month)[1]
        month_end = month_start.replace(day=last_day)
        view_start_date = month_start
        view_end_date = month_end
    else:
        week_param = request.GET.get('week')
        if week_param:
            try:
                week_start = datetime.strptime(week_param, '%Y-%m-%d').date()
                week_start = week_start - timedelta(days=(week_start.weekday()))
            except Exception:
                week_start = today - timedelta(days=(today.weekday()))
        else:
            week_start = today - timedelta(days=(today.weekday()))
        view_start_date = week_start
        view_end_date = week_start + timedelta(days=6)
    
    # Expand range to include all slots (add 60 days buffer for slot ranges)
    holiday_range_start = view_start_date - timedelta(days=30)
    holiday_range_end = view_end_date + timedelta(days=30)
    
    # Pre-fetch all holidays from database for this range
    db_holidays_by_date = {}
    for h in Holiday.objects.filter(date__gte=holiday_range_start, date__lte=holiday_range_end):
        db_holidays_by_date[h.date] = h.name
    
    # Pre-fetch recurring holidays
    recurring_holidays = {}
    for h in Holiday.objects.filter(recurring=True):
        recurring_holidays[(h.date.month, h.date.day)] = h.name
    
    # Pre-compute US holidays using holidays library
    us_holidays_cache = {}
    try:
        import holidays
        us_holidays = holidays.UnitedStates()
        current_check = holiday_range_start
        while current_check <= holiday_range_end:
            holiday_name = us_holidays.get(current_check)
            display_name = Holiday.match_us_federal_holiday(holiday_name)
            if display_name:
                us_holidays_cache[current_check] = display_name
            current_check += timedelta(days=1)
    except ImportError:
        pass
    
    # Create cached holiday check functions
    def is_holiday_cached(check_date):
        """Check if a date is a holiday using cached data."""
        # Check US holidays cache
        if check_date in us_holidays_cache:
            return True
        # Check database holidays
        if check_date in db_holidays_by_date:
            return True
        # Check recurring holidays
        if (check_date.month, check_date.day) in recurring_holidays:
            return True
        return False
    
    def get_holiday_name_cached(check_date):
        """Get holiday name for a date using cached data."""
        # Check US holidays first
        if check_date in us_holidays_cache:
            return us_holidays_cache[check_date]
        # Check database holidays
        if check_date in db_holidays_by_date:
            return db_holidays_by_date[check_date]
        # Check recurring holidays
        if (check_date.month, check_date.day) in recurring_holidays:
            return recurring_holidays[(check_date.month, check_date.day)]
        return None
    
    # Helper function to check if a date is a workday (weekday and not a holiday)
    def is_workday(check_date):
        """Check if a date is a workday (Monday-Friday, not a holiday)."""
        # Check if it's a weekend (Saturday=5, Sunday=6)
        if check_date.weekday() >= 5:
            return False
        # Check if it's a holiday using cached function
        if is_holiday_cached(check_date):
            return False
        return True
    
    # Now generate display dates based on view mode (using already calculated view_start_date and view_end_date)
    if view_mode == 'month':
        # Generate all days in the month (including weekends and holidays)
        display_dates = []
        date_info = []  # List of dicts with date and holiday info
        current_date = view_start_date
        while current_date <= view_end_date:
            display_dates.append(current_date)
            holiday_name = get_holiday_name_cached(current_date)
            date_info.append({
                'date': current_date,
                'is_workday': is_workday(current_date),
                'is_weekend': current_date.weekday() >= 5,
                'is_holiday': holiday_name is not None,
                'holiday_name': holiday_name,
            })
            current_date += timedelta(days=1)
        
        # For context
        prev_view = (view_start_date - timedelta(days=1)).replace(day=1)
        if view_start_date.month == 12:
            next_view = date(view_start_date.year + 1, 1, 1)
        else:
            next_view = date(view_start_date.year, view_start_date.month + 1, 1)
    else:
        # Generate all days for the week (Monday-Sunday)
        display_dates = []
        date_info = []  # List of dicts with date and holiday info
        for i in range(7):
            d = view_start_date + timedelta(days=i)
            display_dates.append(d)
            holiday_name = get_holiday_name_cached(d)
            date_info.append({
                'date': d,
                'is_workday': is_workday(d),
                'is_weekend': d.weekday() >= 5,
                'is_holiday': holiday_name is not None,
                'holiday_name': holiday_name,
            })
        
        # For context
        prev_view = view_start_date - timedelta(days=7)
        next_view = view_start_date + timedelta(days=7)
    
    week_start_date = display_dates[0]
    week_end_date = display_dates[-1]

    # Get event filter and team filter from query parameters
    event_filter = request.GET.get('filter', '').strip()
    team_filter = request.GET.get('team', '').strip()

    # Gather slots overlapping week (across all jobs)
    from collections import defaultdict
    schedule = defaultdict(lambda: defaultdict(list))
    phase_label = {'template': 'Template', 'fabrication': 'Fab', 'install': 'Install', 'extra': 'Extra'}
    # Filter slots that overlap with the week
    # A slot overlaps if: (start_date <= week_end) AND (end_date >= week_start OR end_date is None)
    # This works for all event types: top, remodel, delivery
    slots_query = TopScheduleSlot.objects.select_related('team', 'job', 'job_top').filter(
        # Slots with end_date that overlap the week (start_date <= week_end AND end_date >= week_start)
        Q(end_date__isnull=False) & Q(start_date__lte=week_end_date) & Q(end_date__gte=week_start_date)
        |
        # Single-day slots (no end_date) that fall within the week
        Q(end_date__isnull=True) & Q(start_date__gte=week_start_date) & Q(start_date__lte=week_end_date)
    )
    
    # Apply event type filter
    if event_filter == 'top':
        # Filter for top entries only (job_top is not null)
        slots_query = slots_query.filter(job_top__isnull=False)
    elif event_filter in ['remodel', 'delivery']:
        # Filter by event_type for standalone events
        slots_query = slots_query.filter(event_type=event_filter, job_top__isnull=True)
    
    # Apply team filter
    if team_filter:
        try:
            team_id = int(team_filter)
            slots_query = slots_query.filter(team_id=team_id)
        except (ValueError, TypeError):
            pass  # Invalid team filter, ignore it
    
    slots = slots_query
    assigned_team_ids = set()
    
    # Process all slots (top, remodel, delivery) and expand date ranges
    # This applies to all event types: slots with date ranges will appear on all days they cover
    for s in slots:
        # For standalone events (remodel/delivery), use event_type in the label
        if not s.job_top:
            inside = s.note or s.event_type.title()
        else:
            # For top entry slots, use note or phase
            inside = s.note or phase_label.get(s.phase, s.phase)
        label = f"{s.job.job_code}[{inside}]"
        
        # Determine the date range for this slot (works for all event types)
        slot_start = s.start_date
        slot_end = s.end_date if s.end_date else s.start_date  # Use start_date as end_date if end_date is None
        
        # Generate all dates from slot_start to slot_end (inclusive)
        # This expands the slot to show on every day in its date range
        # Count all workdays in the slot range (even if outside displayed week)
        # Only display dates that are workdays AND within the displayed week
        current_date = slot_start
        day_number = 1  # Start counting from Day1 (workdays only)
        while current_date <= slot_end:
            # Check if it's a workday first
            if is_workday(current_date):
                # Only add dates that fall within the displayed week
                if week_start_date <= current_date <= week_end_date:
                    # Append day indicator to the label (Day1, Day2, etc.)
                    label_with_day = f"{label} - Day{day_number}"
                    schedule[s.team_id][current_date].append({'label': label_with_day, 'id': s.id, 'confirmed': s.confirmed, 'job_id': s.job_id})
                # Increment day counter for all workdays (even if outside displayed week)
                day_number += 1
            # Move to next date (but don't increment day_number for weekends/holidays)
            current_date += timedelta(days=1)
        
        assigned_team_ids.add(s.team_id)

    # Build rows for template
    # If team filter is active, only show that team; otherwise show all teams with slots
    if team_filter:
        try:
            team_id = int(team_filter)
            teams_for_schedule = [t for t in teams if t.id == team_id and t.id in assigned_team_ids]
        except (ValueError, TypeError):
            teams_for_schedule = [t for t in teams if t.id in assigned_team_ids]
    else:
        teams_for_schedule = [t for t in teams if t.id in assigned_team_ids]
    
    schedule_rows = []
    for t in teams_for_schedule:
        team_map = schedule.get(t.id, {})
        cells = []
        for i, d in enumerate(display_dates):
            cells.append({
                'items': team_map.get(d, []),
                'date_info': date_info[i] if i < len(date_info) else None
            })
        schedule_rows.append({'team': t, 'cells': cells})

    return render(request, 'job/master_scheduler.html', {
        'display_dates': display_dates,
        'date_info': date_info,
        'view_mode': view_mode,
        'view_start_date': view_start_date,
        'view_end_date': view_end_date,
        'prev_view': prev_view,
        'next_view': next_view,
        'schedule_rows': schedule_rows,
        'event_filter': event_filter,
        'team_filter': team_filter,
        'teams': teams,
    })


# -----------------------------
# Carpenter progress views
# -----------------------------
def job_sitework_carpenter(request, job_id):
    """Carpenter screen: show all sitework lines with qty>0 and allow progress updates."""
    job = get_object_or_404(Job, id=job_id)
    # Prefer primary sitework quote; fallback to latest
    primary = job.sitework_quotes.filter(is_primary=True).first()
    sitework_quote = primary or job.sitework_quotes.order_by('-id').first()

    if sitework_quote:
        lines = list(
            SiteworkQuoteLine.objects.filter(quote=sitework_quote, quantity__gt=0)
            .select_related('cat')
            .order_by('cat__orderby', 'orderby', 'id')
        )
        line_ids = [l.id for l in lines]
        progress_map = {p.line_id: p for p in SiteworkLineProgress.objects.filter(line_id__in=line_ids)}
        grouped = {}
        for l in lines:
            grouped.setdefault(l.cat, []).append(l)
    else:
        progress_map = {}
        grouped = {}

    context = {
        'job': job,
        'sitework_quote': sitework_quote,
        'grouped': grouped,
        'progress_map': progress_map,
        'progress_choices': [0, 25, 50, 75, 100],
    }
    return render(request, 'job/job_carpenter.html', context)


@require_POST
def job_set_sitework_line_progress(request, job_id):
    """AJAX endpoint to set progress for a single sitework line."""
    job = get_object_or_404(Job, id=job_id)
    primary = job.sitework_quotes.filter(is_primary=True).first()
    sitework_quote = primary or job.sitework_quotes.order_by('-id').first()
    if not sitework_quote:
        return JsonResponse({'success': False, 'error': 'No sitework quote found.'}, status=400)

    try:
        line_id = int(request.POST.get('line_id', '0'))
        progress = int(request.POST.get('progress', '0'))
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid parameters.'}, status=400)

    # Clamp to allowed values
    allowed = {0, 25, 50, 75, 100}
    if progress not in allowed:
        # Snap to nearest allowed
        progress = min(allowed, key=lambda a: abs(a - progress))

    line = get_object_or_404(SiteworkQuoteLine, id=line_id)
    if line.quote_id != sitework_quote.id:
        return JsonResponse({'success': False, 'error': 'Line not in current quote.'}, status=400)

    progress_obj, _ = SiteworkLineProgress.objects.get_or_create(line=line)
    progress_obj.progress_percent = progress
    # Update note if present
    if 'note' in request.POST:
        progress_obj.note = request.POST.get('note', '')
    if request.user and request.user.is_authenticated:
        progress_obj.updated_by = request.user
    progress_obj.updated_at = timezone.now()
    progress_obj.save()

    return JsonResponse({'success': True, 'progress': progress, 'note': progress_obj.note or ''})

# -----------------------------
# Attachments views
# -----------------------------
def job_attachments(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    if request.method == 'POST' and request.FILES.getlist('files'):
        uploaded_files = request.FILES.getlist('files')
        title = request.POST.get('title', '')
        
        uploaded_count = 0
        for uploaded_file in uploaded_files:
            att = JobAttachment(job=job, file=uploaded_file, title=title)
            if request.user and request.user.is_authenticated:
                att.uploaded_by = request.user
            att.save()
            uploaded_count += 1
        
        if uploaded_count == 1:
            messages.success(request, 'File uploaded successfully.')
        else:
            messages.success(request, f'{uploaded_count} files uploaded successfully.')
        return redirect('job:job_attachments', job_id=job.id)

    attachments = job.attachments.all()
    return render(request, 'job/job_attachments.html', {
        'job': job,
        'attachments': attachments,
    })


def _job_attachment_file_response(job_id, attachment_id, as_attachment=False):
    job = get_object_or_404(Job, id=job_id)
    att = get_object_or_404(JobAttachment, id=attachment_id, job=job)
    if not att.file:
        raise Http404('Attachment file not found.')

    filename = os.path.basename(att.file.name)
    content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    try:
        att.file.open('rb')
    except Exception as exc:
        raise Http404('Attachment file not found.') from exc

    return FileResponse(
        att.file,
        as_attachment=as_attachment,
        filename=filename,
        content_type=content_type,
    )


@login_required
def job_attachment_open(request, job_id, attachment_id):
    return _job_attachment_file_response(job_id, attachment_id, as_attachment=False)


@login_required
def job_attachment_download(request, job_id, attachment_id):
    return _job_attachment_file_response(job_id, attachment_id, as_attachment=True)


@require_POST
def job_attachment_delete(request, job_id, attachment_id):
    job = get_object_or_404(Job, id=job_id)
    att = get_object_or_404(JobAttachment, id=attachment_id, job=job)
    # Delete file from storage first
    try:
        storage = att.file.storage
        name = att.file.name
        att.delete()
        if name and storage.exists(name):
            storage.delete(name)
    except Exception:
        # If storage delete fails, the DB row is already gone
        pass
    messages.success(request, 'Attachment deleted.')
    return redirect('job:job_attachments', job_id=job.id)

class JobListView(LoginRequiredMixin, ListView):
    """View to list all jobs with client-side search functionality."""
    model = Job
    template_name = 'job/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 20
    
    def get_status_filter(self):
        status = self.request.GET.get('status', 'active')
        if status in ('active', 'inactive', 'all'):
            return status
        return 'active'

    def get_queryset(self):
        queryset = Job.objects.select_related('customer').prefetch_related('product_quotes', 'sitework_quotes')
        status = self.get_status_filter()
        if status == 'active':
            queryset = queryset.filter(active=True)
        elif status == 'inactive':
            queryset = queryset.filter(active=False)
        return queryset.order_by('-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add counts for status display - optimized with single aggregation query
        from django.db.models import Count, Q
        counts = Job.objects.aggregate(
            total_jobs=Count('id'),
            active_jobs=Count('id', filter=Q(active=True)),
            sold_jobs=Count('id', filter=Q(sold=True))
        )
        context['active_jobs'] = counts['active_jobs']
        context['sold_jobs'] = counts['sold_jobs']
        context['total_jobs'] = counts['total_jobs']
        context['status_filter'] = self.get_status_filter()
        return context


class JobQuotesView(DetailView):
    """View to show job quotes and product quotes."""
    model = Job
    template_name = 'job/job_quotes.html'
    context_object_name = 'job'
    
    def get_queryset(self):
        return Job.objects.select_related('customer').prefetch_related(
            'product_quotes', 'sitework_quotes'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.get_object()
        
        # Removed total_cost calculation
        context['product_quotes'] = job.product_quotes.all()
        context['active_product_quotes'] = job.product_quotes.filter(status='A')
        
        # Add current sitework quote if it exists
        sitework_quote = SiteworkQuote.objects.filter(job=job).order_by('-id').first()
        if sitework_quote:
            context['sitework_quote'] = sitework_quote
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle POST request to add a new quote."""
        job = self.get_object()
        
        quote_name = request.POST.get('quote_name')
        quote_date = request.POST.get('quote_date')
        
        if not quote_name:
            messages.error(request, 'Quote name is required.')
            return self.get(request, *args, **kwargs)
        
        try:
            from product.models import ProductQuote
            
            # Create the product quote using the job's customer
            product_quote = ProductQuote.objects.create(
                name=quote_name,
                customer=job.customer,  # Fixed to job's customer
                job=job,
                status='A',  # Active
                quoted_date=quote_date or timezone.now().date(),
                subtotal=0
            )
            
            messages.success(request, f'Quote "{quote_name}" created successfully!')
            return redirect('job:job_quotes', pk=job.pk)
            
        except Exception as e:
            messages.error(request, f'Error creating quote: {str(e)}')
        
        return self.get(request, *args, **kwargs)


class JobCreateView(LoginRequiredMixin, CreateView):
    """Enhanced view to create a new job with better UX."""
    model = Job
    form_class = JobCreateForm
    template_name = 'job/job_create.html'
    success_url = reverse_lazy('job:job_list')
    
    def form_valid(self, form):
        """Handle form submission with enhanced validation."""
        try:
            # Set default values
            form.instance.active = True  # New jobs are active by default
            
            # Save the job
            job = form.save()

            if job.sold:
                from .sales_from_quote import sync_sales_when_job_sold
                sync_sales_when_job_sold(job, self.request.user)
            
            # Generate job code if not provided
            if not job.job_code:
                job.save()  # This will trigger the auto-generation
            
            messages.success(
                self.request, 
                f'Job "{job.job_code}" created successfully for {job.customer}.'
            )
            
            # Redirect to job detail instead of list
            return redirect('job:job_detail', pk=job.pk)
            
        except Exception as e:
            messages.error(self.request, f'Error creating job: {str(e)}')
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        
        # Add Google Maps API keys from settings for address autocomplete
        from django.conf import settings
        google_places_api_key = getattr(settings, 'GOOGLE_PLACES_API_KEY', '')
        
        context.update({
            'title': 'Create New Job',
            'button_text': 'Create Job',
            'is_create': True,
            'customers': Customer.objects.all().order_by('last_name', 'first_name'),
            'job_types': JobType.objects.filter(status='A').order_by('name'),
            'store_locations': StoreLocation.objects.all().order_by('name'),
            'users': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
            'counties': County.objects.all().order_by('name'),
            'google_places_api_key': google_places_api_key,
        })
        return context
    
    def get_form(self, form_class=None):
        """Customize form with better initial data."""
        form = super().get_form(form_class)
        
        # Set better defaults
        form.fields['active'].initial = True
        form.fields['sold'].initial = False
        
        # Make customer field required
        form.fields['customer'].required = True
        
        return form

    def form_invalid(self, form):
        hints = []
        for field_name, errors in form.errors.items():
            if field_name == '__all__':
                for error in errors:
                    hints.append(str(error))
                continue
            label = form.fields[field_name].label if field_name in form.fields else field_name.replace('_', ' ').title()
            hints.append(f'{label}: {errors[0]}')
        if hints:
            messages.error(
                self.request,
                'Could not create job. ' + ' '.join(hints),
            )
        return super().form_invalid(form)


class JobUpdateView(UpdateView):
    """View to update an existing job."""
    model = Job
    form_class = JobCreateForm
    template_name = 'job/job_create.html'
    success_url = reverse_lazy('job:job_list')
    
    def form_valid(self, form):
        was_sold = self.object.sold if self.object.pk else False
        response = super().form_valid(form)
        if self.object.sold and not was_sold:
            from .sales_from_quote import sync_sales_when_job_sold
            sync_sales_when_job_sold(self.object, self.request.user)
        messages.success(self.request, 'Job updated successfully.')
        return response

    def form_invalid(self, form):
        hints = []
        for field_name, errors in form.errors.items():
            if field_name == '__all__':
                for error in errors:
                    hints.append(str(error))
                continue
            label = form.fields[field_name].label if field_name in form.fields else field_name.replace('_', ' ').title()
            hints.append(f'{label}: {errors[0]}')
        if hints:
            messages.error(
                self.request,
                'Could not update job. ' + ' '.join(hints),
            )
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Job'
        context['button_text'] = 'Update Job'
        
        # Add Google Maps API keys from settings for address autocomplete
        from django.conf import settings
        context.update({
            'customers': Customer.objects.all().order_by('last_name', 'first_name'),
            'job_types': JobType.objects.filter(status='A').order_by('name'),
            'store_locations': StoreLocation.objects.all().order_by('name'),
            'users': User.objects.filter(is_active=True).order_by('first_name', 'last_name'),
            'counties': County.objects.all().order_by('name'),
            'google_places_api_key': getattr(settings, 'GOOGLE_PLACES_API_KEY', ''),
        })
        
        return context


@login_required
@require_POST
def job_delete(request, pk):
    """Delete a job after POST confirmation from the job list."""
    job = get_object_or_404(Job, pk=pk)
    job_code = job.job_code or job.pk
    job.delete()
    messages.success(request, f'Job "{job_code}" deleted successfully.')
    return redirect('job:job_list')


@require_POST
def add_product_quote_to_job(request, job_id):
    """Add a product quote to a job."""
    job = get_object_or_404(Job, id=job_id)
    form = JobProductQuoteForm(request.POST, job=job)
    
    if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
        # AJAX request from job products page
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid form data'})
    else:
        # Regular form submission
        if form.is_valid():
            form.save()
            messages.success(request, 'Product quote added to job successfully.')
        else:
            messages.error(request, 'Error adding product quote to job.')
        
        return redirect('job:job_detail', pk=job_id)


def job_product_quote_create(request, job_id):
    """Create a new product quote for a job."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method == 'POST':
        form = JobProductQuoteForm(request.POST, job=job)
        if form.is_valid():
            product_quote = form.save(commit=False)
            product_quote.customer = job.customer  # Set customer from job
            product_quote.job = job
            product_quote.save()
            
            messages.success(request, 'Product quote created successfully.')
            return redirect('job:job_quotes', pk=job_id)
    else:
        form = JobProductQuoteForm(job=job)
        form.fields['name'].initial = f"Product Quote for {job.job_code}"
    
    # Style widgets for consistent UI
    try:
        form.fields['name'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['status'].widget.attrs.update({'class': 'form-select form-select-sm'})
        form.fields['comments'].widget.attrs.update({'class': 'form-control form-control-sm', 'rows': 3})
    except Exception:
        pass
    
    return render(request, 'job/job_product_quote_form.html', {
        'job': job,
        'form': form,
        'action': 'create'
    })


def job_product_quote_update(request, job_id, quote_id=None):
    """Update an existing product quote for a job."""
    job = get_object_or_404(Job, id=job_id)
    
    # If quote_id is provided, get that specific quote, otherwise get the latest
    if quote_id:
        product_quote = get_object_or_404(ProductQuote, id=quote_id, job=job)
    else:
        product_quote = ProductQuote.objects.filter(job=job).order_by('-id').first()
        if not product_quote:
            messages.error(request, 'No product quote found for this job.')
            return redirect('job:job_quotes', pk=job_id)
    
    if request.method == 'POST':
        form = JobProductQuoteForm(request.POST, instance=product_quote, job=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product quote updated successfully.')
            return redirect('job:job_quotes', pk=job_id)
    else:
        form = JobProductQuoteForm(instance=product_quote, job=job)
    
    # Style widgets for consistent UI
    try:
        form.fields['name'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['status'].widget.attrs.update({'class': 'form-select form-select-sm'})
        form.fields['comments'].widget.attrs.update({'class': 'form-control form-control-sm', 'rows': 3})
    except Exception:
        pass
    
    return render(request, 'job/job_product_quote_form.html', {
        'job': job,
        'form': form,
        'product_quote': product_quote,
        'action': 'update'
    })


@require_POST
def remove_product_quote_from_job(request, job_id, quote_id):
    """Remove a product quote from a job."""
    from product.models import ProductQuote
    job = get_object_or_404(Job, id=job_id)
    product_quote = get_object_or_404(ProductQuote, id=quote_id, job=job)
    
    product_quote.delete()
    messages.success(request, 'Product quote removed from job successfully.')
    
    return redirect('job:job_detail', pk=job_id)


@method_decorator(csrf_exempt, name='dispatch')
class JobAutocompleteView(ListView):
    """AJAX view for job autocomplete."""
    model = Job
    template_name = 'job/job_autocomplete.html'
    
    def get_queryset(self):
        query = self.request.GET.get('q', '')
        if query:
            return Job.objects.filter(
                Q(job_code__icontains=query) |
                Q(customer__first_name__icontains=query) |
                Q(customer__last_name__icontains=query) |
                Q(job_description__icontains=query)
            )[:10]
        return Job.objects.none()
    
    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            jobs = []
            for job in context['object_list']:
                jobs.append({
                    'id': job.id,
                    'job_code': job.job_code,
                    'customer': str(job.customer),
                    'description': job.job_description[:50] + '...' if len(job.job_description) > 50 else job.job_description,
                    'status': job.get_status_display(),
                })
            return JsonResponse({'jobs': jobs})
        return super().render_to_response(context, **response_kwargs)







def job_products(request, job_id):
    """View to manage products in a job and allow searching for new products."""
    job = get_object_or_404(Job, id=job_id)
    
    # Get all products for search
    from product.models import Product
    products = Product.objects.all()
    
    # Handle search filters
    keywords = request.GET.get('keywords')
    category = request.GET.get('category')
    manufacturer = request.GET.get('manufacturer')
    
    if keywords:
        products = products.filter(
            Q(part_no__icontains=keywords) |
            Q(description__icontains=keywords)
        )
    
    if category:
        products = products.filter(category_id=category)
    
    if manufacturer:
        products = products.filter(manufacturer_id=manufacturer)
    
    # Get categories and manufacturers for filters
    from product.models import ProductCategory, Manufacturer
    categories = ProductCategory.objects.all()
    manufacturers = Manufacturer.objects.all()
    
    # Get existing product quotes for this job
    existing_quotes = job.product_quotes.all()
    
    context = {
        'job': job,
        'products': products[:50],  # Limit to 50 for performance
        'categories': categories,
        'manufacturers': manufacturers,
        'existing_quotes': existing_quotes,
    }
    
    return render(request, 'job/job_products.html', context)


@require_POST
def add_product_to_job_ajax(request, job_id):
    """AJAX view to add a product to a job by creating or updating a product quote."""
    job = get_object_or_404(Job, id=job_id)
    
    try:
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        
        if not product_id:
            return JsonResponse({'success': False, 'error': 'Product ID is required'})
        
        # Get the product
        from product.models import Product
        product = get_object_or_404(Product, id=product_id)
        
        # Check if there's already a product quote for this job and customer
        from product.models import ProductQuote
        existing_quote = None
        for job_product_quote in job.product_quotes.all():
            if job_product_quote.product_quote.customer == job.customer:
                existing_quote = job_product_quote.product_quote
                break
        
        # If no existing quote, create a new one
        if not existing_quote:
            existing_quote = ProductQuote.objects.create(
                name=f"Job {job.job_code} Products",
                customer=job.customer,
                job=job,
                status='A',
                subtotal=0
            )
        
        # Add or update the product in the quote
        from product.models import ProductQuoteLine
        line_item, created = ProductQuoteLine.objects.get_or_create(
            quote=existing_quote,
            product=product,
            defaults={
                'quantity': quantity,
                'price_type': 'retail_sell',  # Default to retail_sell
                'product_description': product.description,
            }
        )
        
        if not created:
            # Update the quantity if the product already exists
            line_item.quantity += quantity
            line_item.save()
        
        # Recalculate the quote subtotal
        existing_quote.calculate_subtotal()
        
        return JsonResponse({
            'success': True,
            'message': f'Product {product.part_no} added to job successfully (quantity: {line_item.quantity})',
            'product_quote_id': existing_quote.id,
            'product_name': product.part_no,
            'quantity': line_item.quantity,
            'total_price': float(existing_quote.subtotal)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


class JobDetailUpdateView(DetailView):
    """View to show and edit job details with database-bound fields."""
    model = Job
    template_name = 'job/job_detail.html'
    context_object_name = 'job'
    
    def get_queryset(self):
        return Job.objects.select_related(
            'customer', 'jobtype', 'storelocation', 'soldby', 
            'coordinator', 'carpenter', 'county'
        ).prefetch_related('product_quotes', 'sitework_quotes')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Use self.object instead of get_object() to avoid duplicate queries
        # self.object is already set by the parent class's get_context_data
        job = self.object
        
        # Job tab is always editable — no separate view/edit switch.
        context['form'] = JobForm(instance=job)
        context['is_edit_mode'] = True
        
        # Add related data for dropdowns
        context['users'] = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        context['job_types'] = JobType.objects.filter(status='A').order_by('name')
        context['store_locations'] = StoreLocation.objects.all().order_by('name')
        context['counties'] = County.objects.all().order_by('name')
        
        # Add other jobs for the same customer (excluding current job)
        # Use customer_id to avoid accessing job.customer which is already prefetched
        context['customer_jobs'] = Job.objects.filter(customer_id=job.customer_id).exclude(pk=job.pk).order_by('-id')
        
        # Add top schedule slots (associated with job_top, not standalone events)
        from .models import TopScheduleSlot
        context['top_schedule_slots'] = TopScheduleSlot.objects.filter(
            job_id=job.pk, 
            job_top__isnull=False
        ).select_related('job_top', 'team').order_by('start_date', 'end_date', 'id')
        
        # Add Google Maps API keys from settings
        from django.conf import settings
        context['google_maps_api_key'] = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
        context['google_places_api_key'] = getattr(settings, 'GOOGLE_PLACES_API_KEY', '')
        
        # Add JOB_SUFFIX_CHOICES for the job code suffix dropdown
        context['job_suffix_choices'] = Job.JOB_SUFFIX_CHOICES
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle form submission for updates."""
        self.object = self.get_object()
        form = JobForm(request.POST, instance=self.object)

        if form.is_valid():
            was_sold = self.object.sold
            job_instance = form.save(commit=False)

            # Handle job_code update from letter suffix dropdown or hidden full code
            job_code_suffix = (request.POST.get('job_code_suffix') or '').strip()
            posted_job_code = (request.POST.get('job_code') or '').strip()
            if job_code_suffix:
                if not job_instance.customer.cust_code:
                    job_instance.customer.save()
                    job_instance.customer.refresh_from_db()

                cust_code = job_instance.customer.cust_code or "XXXXX"
                job_instance.job_code = f"{cust_code}-{job_code_suffix}"
            elif posted_job_code:
                job_instance.job_code = posted_job_code
            elif not job_instance.job_code:
                job_instance.job_code = Job.generate_job_code_for_customer(
                    job_instance.customer,
                    exclude_job_id=job_instance.pk,
                )

            job_instance.save()
            if job_instance.sold and not was_sold:
                from .sales_from_quote import sync_sales_when_job_sold
                sync_sales_when_job_sold(job_instance, request.user)
            messages.success(request, 'Job updated successfully!')
            return redirect('job:job_detail', pk=self.object.pk)
        else:
            context = self.get_context_data()
            context['form'] = form
            context['is_edit_mode'] = True
            return self.render_to_response(context)


def job_detail(request, pk):
    """View to render the job detail template with real job data."""
    from django.shortcuts import get_object_or_404
    from job.models import Job
    
    # Get the job from database with all related data
    job = get_object_or_404(
        Job.objects.select_related(
            'customer', 'jobtype', 'storelocation', 'soldby', 
            'coordinator', 'carpenter', 'county'
        ).prefetch_related('product_quotes', 'sitework_quotes'),
        pk=pk
    )
    
    # Add related data for dropdowns
    users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    job_types = JobType.objects.filter(status='A').order_by('name')
    store_locations = StoreLocation.objects.all().order_by('name')
    counties = County.objects.all().order_by('name')
    
    # Add other jobs for the same customer (excluding current job)
    customer_jobs = Job.objects.filter(customer=job.customer).exclude(pk=job.pk).order_by('-id')
    
    # Add top schedule slots (associated with job_top, not standalone events)
    from .models import TopScheduleSlot
    top_schedule_slots = TopScheduleSlot.objects.filter(
        job=job, 
        job_top__isnull=False
    ).select_related('job_top', 'team').order_by('start_date', 'end_date', 'id')
    
    # Add Google Maps API keys from settings
    from django.conf import settings
    google_maps_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    google_places_api_key = getattr(settings, 'GOOGLE_PLACES_API_KEY', '')
    
    context = {
        'job': job,
        'users': users,
        'job_types': job_types,
        'store_locations': store_locations,
        'counties': counties,
        'is_edit_mode': False,
        'customer_jobs': customer_jobs,
        'top_schedule_slots': top_schedule_slots,
        'google_maps_api_key': google_maps_api_key,
        'google_places_api_key': google_places_api_key,
    }
    
    return render(request, 'job/job_detail.html', context)


def job_quote_products(request, job_id, quote_id):
    """View to manage products in a quote within a job context."""
    from product.models import ProductQuote, Product, ProductCategory, ProductSubCategory1, ProductSubCategory2, Manufacturer, Vendor, ProductImage
    from django.core.paginator import Paginator
    from django.db.models import Q, Prefetch
    
    job = get_object_or_404(Job, id=job_id)
    product_quote = get_object_or_404(ProductQuote, id=quote_id, job=job)

    # Prepare line items with primary images and notes (optimized to avoid N+1 queries)
    line_items = list(
        product_quote.line_items.select_related('product').prefetch_related(
            Prefetch(
                'product__images',
                queryset=ProductImage.objects.filter(is_primary=True),
                to_attr='primary_images'
            )
        )
    )

    notes_qs = JobQuoteProductNotes.objects.filter(
        job=job,
        quote=product_quote,
        line_item_id__in=[line_item.id for line_item in line_items]
    ).order_by('id')
    notes_by_line_item_id = {}
    for note in notes_qs:
        notes_by_line_item_id.setdefault(note.line_item_id, note)

    line_items_with_images = []
    for line_item in line_items:
        primary_images = getattr(line_item.product, 'primary_images', [])
        primary_image = primary_images[0] if primary_images else None
        product_note = notes_by_line_item_id.get(line_item.id)
        line_items_with_images.append((line_item, primary_image, product_note))
    
    # Prepare ad-hoc line items
    adhoc_line_items = list(product_quote.adhoc_line_items.select_related('adhoc'))

    # Initialize querysets for the search
    products = Product.objects.all()
    categories = ProductCategory.objects.all()
    sub_categories1 = ProductSubCategory1.objects.all()
    sub_categories2 = ProductSubCategory2.objects.all()
    manufacturers = Manufacturer.objects.all()
    vendors = Vendor.objects.all()

    # Handle search filters
    keywords = request.GET.get('keywords')
    category = request.GET.get('category')
    sub_category1 = request.GET.get('sub_category1')
    sub_category2 = request.GET.get('sub_category2')
    manufacturer = request.GET.get('manufacturer')
    active_status = request.GET.get('active_status')
    is_ajax = request.GET.get('ajax') == '1'
    sort = request.GET.get('sort')
    order = request.GET.get('order', 'asc')

    # Only show products when search filters are applied
    if any([keywords, category, sub_category1, sub_category2, manufacturer, active_status]):
        if keywords:
            products = products.filter(
                Q(part_no__icontains=keywords) |
                Q(description__icontains=keywords)
            )
        if category:
            products = products.filter(category_id=category)
        if sub_category1:
            products = products.filter(sub_category1_id=sub_category1)
        if sub_category2:
            products = products.filter(sub_category2_id=sub_category2)
        if manufacturer:
            products = products.filter(manufacturer_id=manufacturer)
        if active_status == 'True':
            products = products.filter(status=True)
        elif active_status == 'False':
            products = products.filter(status=False)

        # Optional sorting
        if sort == 'name':
            products = products.order_by('-part_no' if order == 'desc' else 'part_no')
        elif sort == 'retail_price':
            products = products.order_by('-retail_sell' if order == 'desc' else 'retail_sell')
        elif sort == 'builder_price':
            products = products.order_by('-builder_sell' if order == 'desc' else 'builder_sell')

        # Prefetch primary images for search results to avoid per-row image lookups
        products = products.prefetch_related(
            Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_primary=True),
                to_attr='primary_images'
            )
        )

        # Apply pagination
        paginator = Paginator(products, 10)  
        page_number = request.GET.get('page') 
        page_obj = paginator.get_page(page_number) 

        # Prepare products_with_images for the search results
        products_with_images = []
        for product in page_obj:
            primary_images = getattr(product, 'primary_images', [])
            primary_image = primary_images[0] if primary_images else None
            products_with_images.append((product, primary_image))
    else:
        # No filters applied - show empty results
        products_with_images = []
        page_obj = None

    if is_ajax:
        from django.template.loader import render_to_string
        from django.http import HttpResponse
        html = render_to_string('job/_job_quote_product_search_table.html', {
            'products_with_images': products_with_images,
            'page_obj': page_obj,
            'quote': product_quote,
            'job': job,
            'request': request,
            'is_ajax': True,  # Pass flag to template
            'sort': sort,
            'order': order,
        })
        return HttpResponse(html)

    return render(
        request,
        'job/job_quote_products.html',
        {
            'job': job,
            'product_quote': product_quote,
            'page_obj': page_obj,
            'categories': categories, 
            'sub_categories1': sub_categories1,
            'sub_categories2': sub_categories2,
            'manufacturers': manufacturers,
            'line_items_with_images': line_items_with_images,
            'adhoc_line_items': adhoc_line_items,
            'products_with_images': products_with_images,
            'is_ajax': is_ajax,
            'vendors': vendors,
            'sort': sort,
            'order': order,
        }
    )


def add_multiple_products_to_job_quote(request, job_id, quote_id):
    """Job-specific view to add multiple products to a quote that redirects back to job context."""
    import re
    from product.models import ProductQuote, Product, ProductQuoteLine
    
    job = get_object_or_404(Job, id=job_id)
    quote = get_object_or_404(ProductQuote, id=quote_id, job=job)

    if request.method == "POST":
        quantities = {}
        price_types = {}

        for key, value in request.POST.items():
            match = re.match(r'quantities\[(\d+)\]', key)
            if match:
                try:
                    quantities[int(match.group(1))] = int(value or 0)
                except (TypeError, ValueError):
                    quantities[int(match.group(1))] = 0

            match = re.match(r'price_types\[(\d+)\]', key)
            if match:
                price_types[int(match.group(1))] = value

        # Add only products with quantity > 0 (no checkbox selection required)
        for product_id, quantity in quantities.items():
            if quantity <= 0:
                continue
            product = get_object_or_404(Product, id=product_id)
            price_type = price_types.get(product.id, 'retail_sell')
            line_item, created = ProductQuoteLine.objects.get_or_create(
                quote=quote,
                product=product,
                defaults={
                    'quantity': quantity,
                    'price_type': price_type,
                    'product_description': product.description,
                }
            )
            if not created:
                line_item.quantity += quantity
                line_item.save()

        quote.calculate_subtotal()

    # Redirect back to the job quote products page
    return redirect('job:job_quote_products', job_id=job_id, quote_id=quote_id)


# Sitework quote management views for job app
def job_sitework_view(request, job_id):
    """Main sitework view for a job - shows existing sitework quotes."""
    job = get_object_or_404(Job, id=job_id)

    # Refresh stored line prices so Subtotal reflects entered quantities.
    for quote_id in SiteworkQuote.objects.filter(job=job).values_list('id', flat=True):
        SiteworkQuoteLine.objects.calc_price(quote_id)

    # Fetch all sitework quotes for listing (line price sums = subtotal for list display)
    sitework_quotes = (
        SiteworkQuote.objects.filter(job=job)
        .annotate(subtotal_sum=Sum('sql_quotes__price'))
        .order_by('-quotedate')
    )
    
    return render(request, 'job/job_sitework_manage.html', {
        'job': job,
        'sitework_quotes': sitework_quotes,
    })


def _populate_sitework_quote_lines(sitework_quote):
    """Copy active subcategories into quote line items (bulk insert, ~900 rows)."""
    subcats = SiteworkSubCat.objects.filter(
        status="A",
    ).select_related('siteworkcat').order_by('siteworkcat__orderby', 'orderby')

    line_items = [
        SiteworkQuoteLine(
            quote=sitework_quote,
            cat=subcat.siteworkcat,
            subcatkey=subcat.calckey,
            calckey=subcat.calckey,
            quantity=0,
            itemcomment='',
            price=0,
            workdesc=subcat.workdesc,
            quantitydesc=subcat.quantitydesc,
            basecost=subcat.basecost,
            unitamount=subcat.unitamount,
            orderby=subcat.orderby,
            drywall=subcat.drywall,
            allowance=subcat.allowance,
            material=subcat.material,
            labor=subcat.labor,
            profit=subcat.profit,
            subfee=subcat.subfee,
            status=subcat.status,
            kbflag=subcat.kbflag,
            group=subcat.group,
            editallowance=subcat.editallowance,
        )
        for subcat in subcats
    ]
    if line_items:
        SiteworkQuoteLine.objects.bulk_create(line_items, batch_size=500)
    return len(line_items)


def job_sitework_create(request, job_id):
    """Create a new sitework quote for a job."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method == 'POST':
        form = SiteworkQuoteForm(request.POST)
        if form.is_valid():
            sitework_quote = form.save(commit=False)
            sitework_quote.customer = job.customer  # Set customer from job
            sitework_quote.job = job
            # quotedby will be auto-set from job.soldby in the save() method
            sitework_quote.save()

            _populate_sitework_quote_lines(sitework_quote)

            messages.success(request, 'Sitework quote created successfully.')
            return redirect('job:job_sitework', job_id)
    else:
        form = SiteworkQuoteForm()
        # Removed initial values for quotedesc and overheadpercent as requested
        if 'quotedby' in form.fields and request.user.is_authenticated:
            form.fields['quotedby'].initial = request.user.id
    
    # Style widgets for consistent UI
    try:
        form.fields['quotedesc'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['quotedate'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['overheadpercent'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['status'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['kbflag'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['market'].widget.attrs.update({'class': 'form-select form-select-sm'})
        form.fields['quotedby'].widget.attrs.update({'class': 'form-select form-select-sm'})
    except Exception:
        pass
    
    return render(request, 'job/job_sitework_form.html', {
        'job': job,
        'form': form,
        'action': 'create'
    })


def job_sitework_update(request, job_id, quote_id=None):
    """Update an existing sitework quote for a job."""
    job = get_object_or_404(Job, id=job_id)
    
    # If quote_id is provided, get that specific quote
    if quote_id:
        # Try to get quote that belongs to this job, or quote with no job assigned
        sitework_quote = SiteworkQuote.objects.filter(
            id=quote_id
        ).filter(
            Q(job=job) | Q(job__isnull=True)
        ).first()
        
        if not sitework_quote:
            messages.error(request, f'Sitework quote {quote_id} not found or does not belong to this job.')
            return redirect('job:job_sitework', job_id)
        
        # If quote has no job, assign it to this job
        if not sitework_quote.job:
            sitework_quote.job = job
            sitework_quote.save(update_fields=['job'])
    else:
        sitework_quote = SiteworkQuote.objects.filter(job=job).order_by('-id').first()
        if not sitework_quote:
            messages.error(request, 'No sitework quote found for this job.')
            return redirect('job:job_sitework', job_id)
    
    if request.method == 'POST':
        form = SiteworkQuoteForm(request.POST, instance=sitework_quote)
        if form.is_valid():
            quotedby_from_form = form.cleaned_data.get('quotedby')
            sitework_quote = form.save(commit=False)
            sitework_quote.quotedby = quotedby_from_form
            sitework_quote.job = job
            sitework_quote.customer = job.customer
            sitework_quote.save()
            
            messages.success(request, 'Sitework quote updated successfully.')
            return redirect('job:job_sitework', job_id=job_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SiteworkQuoteForm(instance=sitework_quote)
    
    # Style widgets for consistent UI
    try:
        form.fields['quotedesc'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['quotedate'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['overheadpercent'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['status'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['kbflag'].widget.attrs.update({'class': 'form-control form-control-sm'})
        form.fields['market'].widget.attrs.update({'class': 'form-select form-select-sm'})
        form.fields['quotedby'].widget.attrs.update({'class': 'form-select form-select-sm'})
    except Exception:
        pass
    
    return render(request, 'job/job_sitework_form.html', {
        'job': job,
        'form': form,
        'sitework_quote': sitework_quote,
        'action': 'update'
    })


def job_sitework_delete(request, job_id):
    """Delete the sitework quote for a job."""
    job = get_object_or_404(Job, id=job_id)
    sitework_quote = SiteworkQuote.objects.filter(job=job).order_by('-id').first()
    if sitework_quote:
        sitework_quote.delete()
        messages.success(request, 'Sitework quote deleted successfully.')
    else:
        messages.error(request, 'No sitework quote found for this job.')
    
    return redirect('job:job_sitework', job_id)


def job_sitework_quote_pdf_preview(request, job_id, quote_id):
    """Generate PDF preview for sitework quote"""
    from job.pdf_generator_sitework import sitework_quote_pdf_generate
    return sitework_quote_pdf_generate(request, job_id, quote_id)


# Job-specific sitework detail views
def job_sitework_detail(request, job_id, cat):
    """Job-specific version of sitework subcat_form."""
    job = get_object_or_404(Job, id=job_id)
    # Use primary sitework quote if available, otherwise latest quote
    primary_sitework_quote = job.sitework_quotes.filter(is_primary=True).first()
    sitework_quote = primary_sitework_quote or job.sitework_quotes.order_by('-id').first()
    if not sitework_quote:
        messages.error(request, 'No sitework quote found for this job.')
        return redirect('job:job_sitework', job_id)
    
    context = {
        "job": job,
        "cat": cat,
        "qte": sitework_quote.id,
        "qdesc": sitework_quote.quotedesc,
        "qcust": sitework_quote.customer.last_name,
        "first": SiteworkCat.objects.order_by('orderby'),
        "second": SiteworkQuoteLine.objects.filter(cat=cat, quote=sitework_quote.id).order_by('orderby'),
    }
    
    # Build list of quantities for all cats
    mycatcount = {}
    for xcat in SiteworkCat.objects.order_by('orderby'):
        catcount = 0
        for lin in SiteworkQuoteLine.objects.filter(cat=xcat, quote=sitework_quote.id):
            if lin.quantity > 0:
                catcount += 1
        mycatcount[xcat.id] = catcount
    
    context['catcount'] = mycatcount.copy()
    
    return render(request, 'job/job_sitework_detail.html', context)


def job_sitework_qty_popup(request, job_id, cat, subcat, quan):
    """Job-specific version of qty_popup."""
    job = get_object_or_404(Job, id=job_id)
    # Use primary sitework quote if available, otherwise latest quote (align with detail/qty_post)
    primary_sitework_quote = job.sitework_quotes.filter(is_primary=True).first()
    sitework_quote = primary_sitework_quote or job.sitework_quotes.order_by('-id').first()
    if not sitework_quote:
        messages.error(request, 'No sitework quote found for this job.')
        return redirect('job:job_sitework', job_id)
    
    # Try to fetch the existing value, default to 0 if none
    myline = SiteworkQuoteLine.objects.filter(id=subcat, quote=sitework_quote.id).first()
    if myline is None:
        myquan = 0
    else:
        myquan = myline.quantity
    
    myset = {
        "job": job,
        "qte": sitework_quote.id,
        "quote": sitework_quote,
        "cat": SiteworkCat.objects.get(id=cat),
        "subcat": SiteworkQuoteLine.objects.get(id=subcat),
        "quan": myquan,
    }
    
    return render(request, 'job/job_sitework_qty_popup.html', {'data': myset})


def job_sitework_qty_post(request, job_id):
    """Job-specific version of qty_post."""
    job = get_object_or_404(Job, id=job_id)
    # Use primary sitework quote if available, otherwise latest quote
    primary_sitework_quote = job.sitework_quotes.filter(is_primary=True).first()
    sitework_quote = primary_sitework_quote or job.sitework_quotes.order_by('-id').first()
    if not sitework_quote:
        messages.error(request, 'No sitework quote found for this job.')
        return redirect('job:job_sitework', job_id)
    
    context = {}
    x = 0
    s = 0
    q = 0
    c = 0
    
    if request.method == "POST":
        for key, value in request.POST.items():
            if key == 'qtyInput':
                x = int(value)
            if key == 'quoteid':
                q = value
            if key == 'subcat':
                s = value
            if key == 'cat':
                c = value
        
        # Store to the Database: qty, subid, quoteid
        SiteworkQuoteLine.objects.update_qty(x, s, q)

        # Build the context expected by the results template
        try:
            cat_obj = SiteworkCat.objects.get(id=int(c))
        except Exception:
            cat_obj = None
        try:
            subcat_obj = SiteworkQuoteLine.objects.get(id=int(s))
        except Exception:
            subcat_obj = None

        data = {
            "job": job,
            "qte": sitework_quote.id,
            "cat": cat_obj,
            "subcat": subcat_obj,
            "quan": x,
        }

        return render(request, 'job/job_sitework_qty_popup_results.html', {"data": data})
    
    return render(request, 'job/job_sitework_qty_popup_results.html', {"data": {"job": job}})


def job_sitework_comment_popup(request, job_id, subcat, comment):
    """Job-specific version of comment_popup."""
    job = get_object_or_404(Job, id=job_id)
    # Use primary sitework quote if available, otherwise latest quote
    primary_sitework_quote = job.sitework_quotes.filter(is_primary=True).first()
    sitework_quote = primary_sitework_quote or job.sitework_quotes.order_by('-id').first()
    if not sitework_quote:
        messages.error(request, 'No sitework quote found for this job.')
        return redirect('job:job_sitework', job_id)
    
    # Try to fetch the existing comment, default to empty if none
    linecomm = SiteworkQuoteLine.objects.filter(id=subcat, quote=sitework_quote.id).first()
    if linecomm is None:
        mycomm = ""
    else:
        mycomm = linecomm.itemcomment
    
    myset = {
        "job": job,
        "qte": sitework_quote.id,
        "subcat": SiteworkQuoteLine.objects.get(id=subcat),
        "cat": SiteworkQuoteLine.objects.get(id=subcat).cat,
        "comment": mycomm,
    }
    
    return render(request, 'job/job_sitework_comment_popup.html', {'data': myset})


def job_sitework_comment_post(request, job_id):
    """Job-specific version of comment_post."""
    job = get_object_or_404(Job, id=job_id)
    # Use primary sitework quote if available, otherwise latest quote
    primary_sitework_quote = job.sitework_quotes.filter(is_primary=True).first()
    sitework_quote = primary_sitework_quote or job.sitework_quotes.order_by('-id').first()
    if not sitework_quote:
        messages.error(request, 'No sitework quote found for this job.')
        return redirect('job:job_sitework', job_id)
    
    if request.method == "POST":
        comment_val = ""
        subcat_id = 0
        quoteid = 0
        
        for key, value in request.POST.items():
            if key == 'commentInput':
                comment_val = value
            if key == 'subcat':
                subcat_id = value
            if key == 'quoteid':
                quoteid = value
        
        # Update the comment in the database
        SiteworkQuoteLine.objects.update_comment(comment_val, subcat_id, quoteid)

        # Build expected data structure for the results template
        try:
            subcat_obj = SiteworkQuoteLine.objects.get(id=int(subcat_id))
        except Exception:
            subcat_obj = None

        data = {
            'subcat': subcat_obj,
            'comment': comment_val,
            'qte': sitework_quote.id,
        }

        return render(request, 'job/job_sitework_comment_popup_results.html', {
            'job': job,
            'data': data,
        })
    
    return render(request, 'job/job_sitework_comment_popup_results.html', {'job': job, 'data': {}})


# Print preview for Job (markdown + HTML preview)
def job_print_preview(request, job_id):
    """Generate HTML preview of job contract content"""
    from django.shortcuts import get_object_or_404, render
    from job.models import Job, JobQuoteProductNotes
    from job.utils import group_line_items_by_category, group_sitework_by_category, format_currency
    
    job = get_object_or_404(Job, id=job_id)
    
    try:
        # Prepare product data for the template - only show if primary quote exists
        product_quotes_data = []
        primary_product_quote = job.product_quotes.filter(is_primary=True).first()
        
        if primary_product_quote:
            quote = primary_product_quote
            # Calculate tax and total
            tax_rate = quote.get_tax_rate()
            tax_amount = quote.calculate_tax()
            total_with_tax = quote.get_total_with_tax()
            
            # Convert tax rate to percentage for display (e.g., 0.055 -> 5.5)
            tax_rate_percent = float(tax_rate) * 100
            
            quote_data = {
                'name': quote.name,
                'subtotal_price': format_currency(quote.subtotal),
                'subtotal_numeric': float(quote.subtotal),  # For calculation display
                'tax_rate': tax_rate_percent,  # Store as percentage for display
                'tax_amount': format_currency(tax_amount),
                'total_price': format_currency(total_with_tax),
                'categories': []
            }
            
            # Group line items by category
            try:
                categories_data = group_line_items_by_category(quote.line_items.all(), quote.adhoc_line_items.all())
            except Exception as e:
                # If product grouping fails, show empty categories
                categories_data = []
            
            for category in categories_data:
                category_data = {
                    'name': category['name'],
                    'subtotal': category['subtotal'],
                    'items': []
                }
                
                for item_type, item in category['items']:
                    if item_type == 'product':
                        part_no = item.product.part_no or ''
                        description = str(item.product.description or '')
                        # Fetch job-level product note for this line item, if any
                        note_text = ''
                        try:
                            note_obj = JobQuoteProductNotes.objects.filter(job=job, line_item=item).first()
                            if note_obj and note_obj.note:
                                note_text = str(note_obj.note)
                        except Exception:
                            note_text = ''
                    else:
                        part_no = item.adhoc.part_no or ''
                        description = str(item.adhoc.description or '')
                        note_text = ''
                    
                    category_data['items'].append({
                        'part_no': part_no,
                        'quantity': item.quantity,
                        'description': description,
                        'note': note_text
                    })
                
                quote_data['categories'].append(category_data)
            
            product_quotes_data.append(quote_data)
        
        # Prepare sitework data for the template - only show if primary quote exists
        sitework_data = None
        primary_sitework_quote = job.sitework_quotes.filter(is_primary=True).first()
        
        if primary_sitework_quote:
            sitework_quote = primary_sitework_quote
            try:
                categories_data = group_sitework_by_category(sitework_quote)
                
                # Calculate sitework totals
                sitework_subtotal = 0
                for category in categories_data:
                    # Extract numeric value from formatted currency string
                    subtotal_str = category['subtotal'].replace('$', '').replace(',', '')
                    try:
                        sitework_subtotal += float(subtotal_str)
                    except ValueError:
                        pass
                
                # Calculate contingency and overhead
                contingency_pct = 0.05
                overhead_pct = 0.28
                contingency = sitework_subtotal * contingency_pct
                overhead = sitework_subtotal * overhead_pct
                final_total = sitework_subtotal + contingency + overhead
                
                sitework_data = {
                    'subtotal_price': format_currency(sitework_subtotal),
                    'contingency_price': format_currency(contingency),
                    'overhead_price': format_currency(overhead),
                    'total_price': format_currency(final_total),
                    'categories': []
                }
                
                for category in categories_data:
                    category_data = {
                        'name': category['name'],
                        'subtotal': category['subtotal'],
                        'items': []
                    }
                    
                    for item in category['items']:
                        category_data['items'].append({
                            'description': item['workdesc'] or 'N/A',
                            'quantity': item['quantity'],
                            'unit_price': item['unit_amount_str'],
                            'total_price': item['price_str']
                        })
                    
                    sitework_data['categories'].append(category_data)
            except Exception as e:
                sitework_data = None
        
        # Calculate change orders total (only include change orders with amounts)
        change_orders = job.change_orders.all()
        from decimal import Decimal
        change_orders_total = Decimal('0')
        for co in change_orders:
            if co.amount is not None:
                change_orders_total += co.amount
        
        # Calculate total contract amount: Product Quote Total + Sitework Total + Change Orders
        total_contract_amount = Decimal('0')
        for quote_data in product_quotes_data:
            # Extract numeric value from formatted currency string
            total_str = quote_data['total_price'].replace('$', '').replace(',', '')
            try:
                total_contract_amount += Decimal(total_str)
            except (ValueError, TypeError):
                pass
        
        if sitework_data:
            sitework_str = sitework_data['total_price'].replace('$', '').replace(',', '')
            try:
                total_contract_amount += Decimal(sitework_str)
            except (ValueError, TypeError):
                pass
        
        # Add change orders to total
        total_contract_amount += change_orders_total
        
        # Render the template with data
        return render(request, 'job/job_print_preview.html', {
            'job': job,
            'product_quotes_data': product_quotes_data,
            'sitework_data': sitework_data,
            'change_orders_total': format_currency(change_orders_total),
            'change_orders_count': change_orders.count(),
            'total_contract_amount': format_currency(total_contract_amount),
        })
        
    except Exception as e:
        # If generation fails, show error in main template
        import traceback
        print(f"Error in job_print_preview: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return render(request, 'job/job_print_preview.html', {
            'job': job,
            'product_quotes_data': [],
            'sitework_data': None,
            'error': str(e)
        })


def job_pdf_generate(request, job_id):
    """Generate professional PDF using ReportLab for contract-style documents"""
    from job.pdf_generator import job_pdf_generate as generate_pdf
    return generate_pdf(request, job_id)


def job_purchase_order_pdf(request, job_id, po_id):
    """Generate PDF for purchase order with same header/footer as job print preview"""
    from job.pdf_generator import purchase_order_pdf_generate
    
    return purchase_order_pdf_generate(request, job_id, po_id)


def job_purchase_order_email_preview(request, job_id, po_id):
    """Preview email before sending to vendor"""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    
    # Get vendor email
    vendor_email = purchase_order.vendor.contact_email if purchase_order.vendor.contact_email else None
    
    context = {
        'job': job,
        'purchase_order': purchase_order,
        'vendor_email': vendor_email,
    }
    
    return render(request, 'job/job_purchase_order_email_preview.html', context)


@require_POST
def job_purchase_order_email_send(request, job_id, po_id):
    """Send purchase order email to vendor with PDF attachment"""
    from django.core.mail import EmailMessage
    from django.conf import settings
    from io import BytesIO
    import os
    
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    
    # Get vendor email
    vendor_email = purchase_order.vendor.contact_email
    if not vendor_email:
        messages.error(request, 'Vendor does not have an email address configured.')
        return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=po_id)
    
    try:
        # Generate PDF bytes directly
        from job.pdf_generator import purchase_order_pdf_generate
        pdf_response = purchase_order_pdf_generate(request, job_id, po_id)
        
        # Get PDF bytes from response
        if hasattr(pdf_response, 'content'):
            pdf_bytes = pdf_response.content
        else:
            # If it's a file-like object, read it
            pdf_bytes = pdf_response.getvalue() if hasattr(pdf_response, 'getvalue') else b''
        
        if not pdf_bytes:
            messages.error(request, 'Failed to generate PDF. Please try again.')
            return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=po_id)
        
        # Prepare email content
        subject = f'Purchase Order {purchase_order.po_number} - {job.job_code}'
        
        # Get custom email body from form, or use default
        email_body = request.POST.get('email_body', '')
        if not email_body:
            # Fallback to default message if not provided
            email_body = f"""
Dear {purchase_order.vendor.vendor_name or 'Vendor'},

Please find attached Purchase Order {purchase_order.po_number} for Job {job.job_code}.

Please confirm receipt of order, ship date and costs within 3 days.

Thank you for your business.

Best regards,
{request.user.get_full_name() or request.user.username}
Allen Construction Services, Inc.
"""
        
        # Ensure we have a valid from_email
        # Priority: DEFAULT_FROM_EMAIL > EMAIL_HOST_USER > user's email > fallback
        from_email = settings.DEFAULT_FROM_EMAIL
        if not from_email or from_email == 'noreply@example.com':
            from_email = settings.EMAIL_HOST_USER
        if not from_email:
            # Use logged-in user's email as fallback
            from_email = request.user.email
        if not from_email:
            # Final fallback
            from_email = 'noreply@example.com'
        
        # Create email message
        email = EmailMessage(
            subject=subject,
            body=email_body,
            from_email=from_email,
            to=[vendor_email],
        )
        
        # Attach PDF
        email.attach(
            filename=f'purchase_order_{purchase_order.po_number}.pdf',
            content=pdf_bytes,
            mimetype='application/pdf'
        )
        
        # Send email
        email.send(fail_silently=False)
        
        messages.success(request, f'Purchase order email sent successfully to {vendor_email}.')
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        messages.error(request, f'Error sending email: {str(e)}')
        # Log the full error for debugging (in production, use proper logging)
        if settings.DEBUG:
            print(f"Email sending error: {error_details}")
    
    return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=po_id)


@csrf_exempt
def job_print_generate_pdf(request, job_id):
    # For now, simply echo back the posted markdown as a downloadable PDF-like response placeholder
    # In a real implementation, hook into existing product/pdf utilities to render PDF with header
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
        markdown_content = payload.get('markdown_content', '')
    except Exception:
        markdown_content = ''

    # Return as plain text to keep scope minimal; front-end handles download
    response = HttpResponse(markdown_content.encode('utf-8'), content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="job_print_preview.txt"'
    return response


def _get_job_coordinates(job, api_key):
    """Get latitude and longitude for a job location."""
    # Construct full address
    full_address = f"{job.address}, {job.city}, {job.state}"
    if job.zip:
        full_address += f" {job.zip}"
    
    # Get coordinates using Geocoding API
    geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
    geocoding_params = {'address': full_address, 'key': api_key}
    
    response = requests.get(geocoding_url, params=geocoding_params)
    data = response.json()
    
    if data['status'] != 'OK' or not data['results']:
        return None, None, full_address
    
    location = data['results'][0]['geometry']['location']
    return location['lat'], location['lng'], full_address

WEATHER_FORECAST_DAYS = 7


def _forecast_day_label(day_index):
    """Return a short label for a daily forecast slot (Today, Mon, Tue, ...)."""
    if day_index == 0:
        return 'Today'
    from datetime import datetime, timedelta
    forecast_date = datetime.now() + timedelta(days=day_index)
    return forecast_date.strftime('%a')


def _get_current_weather(api_key, lat, lng):
    """Get current weather conditions from Google Weather API."""
    url = "https://weather.googleapis.com/v1/currentConditions:lookup"
    params = {
        'key': api_key,
        'location.latitude': lat,
        'location.longitude': lng,
        'unitsSystem': 'IMPERIAL'
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None, None, None, None
    
    data = response.json()
    if 'weatherCondition' not in data:
        return None, None, None, None
    
    temp = data.get('temperature', {}).get('degrees', 78)
    icon_base = data.get('weatherCondition', {}).get('iconBaseUri')
    condition = data.get('weatherCondition', {}).get('description', {}).get('text', 'Cloudy')
    
    # Format icon URL - ensure it ends with .png
    if icon_base:
        if icon_base.endswith('.png'):
            icon_url = icon_base
        else:
            icon_url = f"{icon_base}.png"
    else:
        icon_url = 'https://maps.gstatic.com/weather/v1/cloudy.png'
    
    return data, temp, condition, icon_url

def _get_hourly_forecast(api_key, lat, lng, current_temp, current_condition, current_weather_icon_url):
    """Get hourly forecast data from Google Weather API."""
    url = "https://weather.googleapis.com/v1/forecast/hours:lookup"
    params = {
        'key': api_key,
        'location.latitude': lat,
        'location.longitude': lng,
        'unitsSystem': 'IMPERIAL',
        'hours': 24
    }
    
    hourly_forecast_data = []
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if 'forecastHours' in data:
                for i, hour in enumerate(data['forecastHours'][:24]):
                    temp = hour.get('temperature', {}).get('degrees', current_temp)
                    condition = hour.get('weatherCondition', {}).get('description', {}).get('text', current_condition)
                    icon_base = hour.get('weatherCondition', {}).get('iconBaseUri')
                    # Format icon URL - ensure it ends with .png
                    if icon_base:
                        if icon_base.endswith('.png'):
                            icon_url = icon_base
                        else:
                            icon_url = f"{icon_base}.png"
                    else:
                        icon_url = None
                    
                    # Extract actual hour from API response
                    display_time = hour.get('displayDateTime', {})
                    hour_value = display_time.get('hours', i) if display_time else i
                    start_time = hour.get('interval', {}).get('startTime', '')
                    
                    hourly_forecast_data.append({
                        'time': hour_value,
                        'start_time': start_time,
                        'temperature': round(temp, 1),
                        'icon_url': icon_url or current_weather_icon_url,
                        'condition': condition
                    })
        else:
            print(f"Hourly forecast API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Hourly forecast API exception: {e}")
    
    # Fallback if hourly API fails
    if not hourly_forecast_data:
        from datetime import datetime, timedelta
        current_time = datetime.now()
        
        for i in range(24):
            future_time = current_time + timedelta(hours=i)
            hour_value = future_time.hour
            temp_variation = 8 * (0.5 - abs(0.5 - (i / 24)))
            hour_temp = current_temp + temp_variation
            
            hourly_forecast_data.append({
                'time': hour_value,
                'start_time': future_time.isoformat(),
                'temperature': round(hour_temp, 1),
                'icon_url': current_weather_icon_url,
                'condition': current_condition
            })
    
    return hourly_forecast_data

def _collect_weather_variations(current_condition, current_weather_icon_url, hourly_forecast_data):
    """Collect unique weather variations from API data."""
    all_weather_variations = []
    
    # Add current weather condition
    all_weather_variations.append({
        'condition': current_condition,
        'icon_url': current_weather_icon_url
    })
    
    # Add hourly forecast conditions for variety
    for hour_data in hourly_forecast_data[:12]:
        condition = hour_data.get('condition')
        icon_url = hour_data.get('icon_url')
        if condition and icon_url:
            variation = {'condition': condition, 'icon_url': icon_url}
            if variation not in all_weather_variations:
                all_weather_variations.append(variation)
    
    return all_weather_variations

def _get_daily_forecast(api_key, lat, lng, current_temp, current_condition, current_weather_icon_url, all_weather_variations):
    """Get daily forecast data from Google Weather API."""
    url = "https://weather.googleapis.com/v1/forecast/days:lookup"
    params = {
        'key': api_key,
        'location.latitude': lat,
        'location.longitude': lng,
        'unitsSystem': 'IMPERIAL',
        'days': WEATHER_FORECAST_DAYS
    }
    
    daily_forecast_data = []
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            
            if 'forecastDays' in data:
                for i, day in enumerate(data['forecastDays'][:WEATHER_FORECAST_DAYS]):
                    # Extract temperature data
                    high_temp = day.get('maxTemperature', {}).get('degrees', current_temp + 8)
                    low_temp = day.get('minTemperature', {}).get('degrees', current_temp - 8)
                    
                    # Extract weather conditions
                    daytime_forecast = day.get('daytimeForecast', {})
                    nighttime_forecast = day.get('nighttimeForecast', {})
                    
                    # Collect weather conditions for variations
                    for forecast_type, forecast_data in [('day', daytime_forecast), ('night', nighttime_forecast)]:
                        if forecast_data.get('weatherCondition'):
                            fc_condition = forecast_data.get('weatherCondition', {}).get('description', {}).get('text')
                            fc_icon_base = forecast_data.get('weatherCondition', {}).get('iconBaseUri')
                            if fc_condition and fc_icon_base:
                                # Format icon URL - ensure it ends with .png
                                if fc_icon_base.endswith('.png'):
                                    fc_icon_url = fc_icon_base
                                else:
                                    fc_icon_url = f"{fc_icon_base}.png"
                                variation = {'condition': fc_condition, 'icon_url': fc_icon_url}
                                if variation not in all_weather_variations:
                                    all_weather_variations.append(variation)
                    
                    # Use daytime condition and icon if available
                    if daytime_forecast.get('weatherCondition'):
                        condition = daytime_forecast.get('weatherCondition', {}).get('description', {}).get('text', current_condition)
                        icon_base = daytime_forecast.get('weatherCondition', {}).get('iconBaseUri')
                    elif nighttime_forecast.get('weatherCondition'):
                        condition = nighttime_forecast.get('weatherCondition', {}).get('description', {}).get('text', current_condition)
                        icon_base = nighttime_forecast.get('weatherCondition', {}).get('iconBaseUri')
                    else:
                        condition = current_condition
                        icon_base = None
                    
                    # Add variety using actual API conditions if repetitive
                    if i > 0 and condition == daily_forecast_data[-1]['condition'] and all_weather_variations:
                        weather_var = all_weather_variations[i % len(all_weather_variations)]
                        condition = weather_var['condition']
                        # Extract icon base from icon_url (remove .png if present)
                        icon_base = weather_var['icon_url'].replace('.png', '') if weather_var['icon_url'].endswith('.png') else weather_var['icon_url']
                    
                    # Format icon URL - ensure it ends with .png
                    if icon_base:
                        if icon_base.endswith('.png'):
                            icon_url = icon_base
                        else:
                            icon_url = f"{icon_base}.png"
                    else:
                        icon_url = current_weather_icon_url
                    
                    date_str = _forecast_day_label(i)
                    
                    daily_forecast_data.append({
                        'date': date_str,
                        'high_temp': round(high_temp),
                        'low_temp': round(low_temp),
                        'icon_url': icon_url,
                        'condition': condition
                    })
        else:
            print(f"Daily forecast API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Daily forecast API exception: {e}")
    
    # Extend to a full week if API returned fewer days
    while len(daily_forecast_data) < WEATHER_FORECAST_DAYS:
        i = len(daily_forecast_data)
        
        # Use pattern from last available forecast or current weather
        if daily_forecast_data:
            last_day = daily_forecast_data[-1]
            base_high = last_day['high_temp'] + (-1 if i % 2 == 0 else 1)
            base_low = last_day['low_temp'] + (-1 if i % 2 == 0 else 1)
            
            # Use diverse conditions from actual API data
            if all_weather_variations:
                weather_var = all_weather_variations[i % len(all_weather_variations)]
                condition = weather_var['condition']
                icon_url = weather_var['icon_url']
            else:
                condition = current_condition
                icon_url = current_weather_icon_url
        else:
            # Fallback if no API data at all
            daily_temp_change = (2 if i % 2 == 0 else -1) + (i * 0.5)
            base_high = current_temp + daily_temp_change + 8
            base_low = current_temp + daily_temp_change - 8
            condition = current_condition
            icon_url = current_weather_icon_url
        
        date_str = _forecast_day_label(i)
        
        daily_forecast_data.append({
            'date': date_str,
            'high_temp': round(base_high),
            'low_temp': round(base_low),
            'icon_url': icon_url,
            'condition': condition
        })
    
    return daily_forecast_data[:WEATHER_FORECAST_DAYS]

def get_weather_data(request, job_id):
    """Get weather data for a job location using Google Maps Weather API."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    try:
        job = get_object_or_404(Job, id=job_id)
        
        # Check if job has address information
        if not (job.address and job.city and job.state):
            return JsonResponse({'error': 'Job location not specified'}, status=400)
        
        # Weather API key (separate from Maps/Places keys)
        api_key = settings.GOOGLE_WEATHER_API_KEY
        if not api_key:
            return JsonResponse({'error': 'Google Weather API key is not configured'}, status=500)
        
        # Get coordinates
        lat, lng, full_address = _get_job_coordinates(job, api_key)
        if lat is None:
            return JsonResponse({'error': 'Could not find coordinates for this address'}, status=400)
        
        # Get current weather
        current_weather_data, current_temp, current_condition, current_weather_icon_url = _get_current_weather(api_key, lat, lng)
        if current_weather_data is None:
            return JsonResponse({'error': 'Could not fetch current weather data'}, status=400)
        

        
        # Get hourly forecast
        hourly_forecast_data = _get_hourly_forecast(api_key, lat, lng, current_temp, current_condition, current_weather_icon_url)
        
        # Collect weather variations and get daily forecast
        all_weather_variations = _collect_weather_variations(current_condition, current_weather_icon_url, hourly_forecast_data)
        daily_forecast_data = _get_daily_forecast(api_key, lat, lng, current_temp, current_condition, current_weather_icon_url, all_weather_variations)


        
        # Extract relevant weather information based on the documented response structure
        weather_info = {
            'location': full_address,
            'temperature': current_weather_data.get('temperature', {}).get('degrees'),
            'temperature_unit': current_weather_data.get('temperature', {}).get('unit'),
            'humidity': current_weather_data.get('relativeHumidity'),
            'condition': current_condition,  # Use actual API condition
            'icon_url': current_weather_icon_url,    # Use actual API icon (properly formatted)
            'wind_speed': current_weather_data.get('wind', {}).get('speed', {}).get('value'),
            'wind_direction': current_weather_data.get('wind', {}).get('direction', {}).get('cardinal'),
            'pressure': current_weather_data.get('airPressure', {}).get('meanSeaLevelMillibars'),
            'datetime': current_weather_data.get('currentTime'),
            'hourly_forecast': hourly_forecast_data,
            'daily_forecast': daily_forecast_data
        }
        
        return JsonResponse({'success': True, 'weather': weather_info})
        
    except Exception as e:
        import traceback
        print("Weather API Error:", str(e))
        print("Traceback:", traceback.format_exc())
        return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)


@require_GET
def ajax_search_jobs(request):
    """AJAX search jobs with pagination and status filtering"""
    query = request.GET.get('q', '').strip()
    search_type = request.GET.get('type', 'job_code')
    status_filter = request.GET.get('status', 'active')
    page = request.GET.get('page', 1)
    
    # Debug logging
    print(f"Job search request - Query: '{query}', Type: {search_type}, Status: {status_filter}, Page: {page}")
    
    jobs = Job.objects.select_related('customer').prefetch_related('product_quotes', 'sitework_quotes')
    
    # Apply status filter
    if status_filter == 'active':
        jobs = jobs.filter(active=True)
        print(f"Filtering for active jobs: {jobs.count()} found")
    elif status_filter == 'inactive':
        jobs = jobs.filter(active=False)
        print(f"Filtering for inactive jobs: {jobs.count()} found")
    elif status_filter == 'all':
        print(f"Showing all jobs: {jobs.count()} found")
    # For 'all', no additional filter is applied
    
    if query:
        if search_type == 'job_code':
            jobs = jobs.filter(Q(job_code__icontains=query))
        elif search_type == 'customer_name':
            jobs = jobs.filter(
                Q(customer__first_name__icontains=query) |
                Q(customer__last_name__icontains=query)
            )
        else:
            jobs = jobs.filter(Q(job_code__icontains=query))
    
    # Pagination for search results
    paginator = Paginator(jobs, 20)  # 20 items per page
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    results = []
    for job in page_obj:
        results.append({
            'id': job.id,
            'job_code': job.job_code or '-',
            'customer': str(job.customer),
            'description': job.job_description or 'No description',
            'active': job.active,
            'sold': job.sold,
            'quotes_url': reverse('job:job_detail', args=[job.id]),
            'edit_url': reverse('job:job_update', args=[job.id]),
            'delete_url': reverse('job:job_delete', args=[job.id]),
        })
    
    return JsonResponse({
        'jobs': results,
        'paginator': {
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'page_range': list(paginator.page_range),
            'current_page': page_obj.number,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        }
    })

def job_customer_detail(request, job_id):
    """View to show customer details within the job context."""
    from crm.models import Customer, Referral, County
    
    job = get_object_or_404(Job, id=job_id)
    customer = job.customer
    
    # Generate cust_code if missing or regenerate it based on current name
    # Calculate what the cust_code should be
    last_name = customer.last_name if customer.last_name else ""
    first_name = customer.first_name if customer.first_name else ""
    
    if last_name:
        last_name_part = last_name[:4].lower().capitalize()
    else:
        last_name_part = ""
    
    if first_name:
        if len(first_name) >= 2:
            first_name_part = first_name[:2].lower().capitalize()
        else:
            first_name_part = first_name.lower().capitalize()
    else:
        first_name_part = ""
    
    expected_cust_code = f"{last_name_part}{first_name_part}"
    
    # Update cust_code if it doesn't match or doesn't exist
    print(f"Customer: Expected cust_code: {expected_cust_code} vs customer.cust_code {customer.cust_code}")
    if not customer.cust_code or customer.cust_code != expected_cust_code:
        customer.cust_code = expected_cust_code
        customer.save(update_fields=['cust_code'])
        customer.refresh_from_db()
    
    context = {
        'job': job,
        'customer': customer,
        'referrals': Referral.objects.all(),
        'counties': County.objects.all(),
    }
    
    return render(request, 'job/job_customer_detail.html', context)


def job_gantt_view(request, job_id):
    """View to display Gantt chart for job milestones."""
    job = get_object_or_404(Job, id=job_id)
    
    context = {
        'job': job,
    }
    
    return render(request, 'job/job_gantt.html', context)


def job_gantt_data(request, job_id):
    """API endpoint to provide Gantt chart data for a job."""
    job = get_object_or_404(Job, id=job_id)
    
    # Map job dates to Gantt tasks
    tasks = []
    task_id = 1
    
    # Define milestones based on job dates
    milestones = [
        {
            'name': 'Job Sold',
            'date_field': 'datesold',
            'type': 'milestone',
            'color': '#FF9800'
        },
        {
            'name': 'Initial Contact',
            'date_field': 'initalcontactdate',
            'type': 'task',
            'color': '#4CAF50'
        },
        {
            'name': 'Initial Measure',
            'date_field': 'initialmeasuredate',
            'type': 'task',
            'color': '#4CAF50'
        },
        {
            'name': 'Project Start',
            'date_field': 'startdate',
            'type': 'task',
            'color': '#2196F3'
        },
        {
            'name': 'Cabinet Order',
            'date_field': 'cabneededdate',
            'type': 'milestone',
            'color': '#FF9800'
        },
        {
            'name': 'Countertop Install',
            'date_field': 'topinstalldate',
            'type': 'task',
            'color': '#4CAF50'
        },
        {
            'name': 'Project Complete',
            'date_field': 'completDate',
            'type': 'milestone',
            'color': '#FF9800'
        }
    ]
    
    for milestone in milestones:
        date_value = getattr(job, milestone['date_field'], None)
        if date_value:
            # For milestones, start and end date are the same
            if milestone['type'] == 'milestone':
                start_date = date_value.strftime('%Y-%m-%d')
                end_date = date_value.strftime('%Y-%m-%d')
            else:
                # For tasks, use the date as start and add estimated duration
                start_date = date_value.strftime('%Y-%m-%d')
                from datetime import timedelta
                end_date = (date_value + timedelta(days=3)).strftime('%Y-%m-%d')
            
            task = {
                'id': task_id,
                'text': milestone['name'],
                'start_date': start_date,
                'end_date': end_date,
                'type': milestone['type'],
                'color': milestone['color'],
                'progress': 0
            }
            tasks.append(task)
            task_id += 1
    
    # Add dependencies (simple sequential dependencies)
    links = []
    for i in range(len(tasks) - 1):
        links.append({
            'id': i + 1,
            'source': tasks[i]['id'],
            'target': tasks[i + 1]['id'],
            'type': '0'  # Finish-to-Start
        })
    
    return JsonResponse({
        'data': tasks,
        'links': links,
        'collections': {
            'links': links
        }
    })


def job_notes(request, job_id):
    """View to display and manage job notes."""
    job = get_object_or_404(Job, id=job_id)
    
    # Get all notes for this job, ordered by most recent first
    notes = JobNotes.objects.filter(job=job).select_related('assigned_to').order_by('-note_date')
    
    # Get all users for assignment dropdown (designers only for notes)
    users = User.objects.filter(
        is_active=True,
        user_roles__role__type='DES',
        user_roles__is_active=True
    ).distinct().order_by('first_name', 'last_name')
    
    if request.method == 'POST':
        # Handle new note creation
        note_text = request.POST.get('note', '').strip()
        assigned_to_id = request.POST.get('assigned_to')
        follow_up_date = request.POST.get('follow_up')
        completed = request.POST.get('completed') == 'on'
        
        if note_text:
            # Create new note
            note = JobNotes.objects.create(
                job=job,
                note=note_text,
                assigned_to_id=assigned_to_id if assigned_to_id else None,
                follow_up=follow_up_date if follow_up_date else None,
                completed=completed
            )
            messages.success(request, 'Note added successfully.')
            return redirect('job:job_notes', job_id=job_id)
        else:
            messages.error(request, 'Note content is required.')
    
    context = {
        'job': job,
        'notes': notes,
        'users': users,
    }
    
    return render(request, 'job/job_notes.html', context)


def job_notes_create(request, job_id):
    """Create a new job note."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method == 'POST':
        note_text = request.POST.get('note', '').strip()
        assigned_to_id = request.POST.get('assigned_to')
        follow_up_date = request.POST.get('follow_up')
        completed = request.POST.get('completed') == 'on'
        
        if note_text:
            # Create new note
            note = JobNotes.objects.create(
                job=job,
                note=note_text,
                assigned_to_id=assigned_to_id if assigned_to_id else None,
                follow_up=follow_up_date if follow_up_date else None,
                completed=completed
            )
            
            messages.success(request, 'Note created successfully.')
            return redirect('job:job_notes', job_id=job_id)
        else:
            messages.error(request, 'Note content is required.')
    
    # Get all users for assignment dropdown (designers only for notes)
    users = User.objects.filter(
        is_active=True,
        user_roles__role__type='DES',
        user_roles__is_active=True
    ).distinct().order_by('first_name', 'last_name')
    
    # Create form data for template
    form_data = {
        'note': '',
        'assigned_to': '',
        'follow_up': '',
        'completed': False
    }
    
    return render(request, 'job/job_notes_form.html', {
        'job': job,
        'form': form_data,
        'users': users,
        'action': 'create'
    })


def job_notes_update(request, job_id, note_id=None):
    """Update an existing job note."""
    job = get_object_or_404(Job, id=job_id)
    
    # If note_id is provided, get that specific note, otherwise get the latest
    if note_id:
        note = get_object_or_404(JobNotes, id=note_id, job=job)
    else:
        note = JobNotes.objects.filter(job=job).order_by('-id').first()
        if not note:
            messages.error(request, 'No note found for this job.')
            return redirect('job:job_notes', job_id=job_id)
    
    if request.method == 'POST':
        note_text = request.POST.get('note', '').strip()
        assigned_to_id = request.POST.get('assigned_to')
        follow_up_date = request.POST.get('follow_up')
        completed = request.POST.get('completed') == 'on'
        
        if note_text:
            # Update note
            note.note = note_text
            note.assigned_to_id = assigned_to_id if assigned_to_id else None
            note.follow_up = follow_up_date if follow_up_date else None
            note.completed = completed
            note.save()
            
            messages.success(request, 'Note updated successfully.')
            return redirect('job:job_notes', job_id=job_id)
        else:
            messages.error(request, 'Note content is required.')
    
    # Get all users for assignment dropdown (designers only for notes)
    users = User.objects.filter(
        is_active=True,
        user_roles__role__type='DES',
        user_roles__is_active=True
    ).distinct().order_by('first_name', 'last_name')
    
    # Create form data for template
    form_data = {
        'note': note.note,
        'assigned_to': note.assigned_to_id,
        'follow_up': note.follow_up.strftime('%Y-%m-%dT%H:%M') if note.follow_up else '',
        'completed': note.completed
    }
    
    return render(request, 'job/job_notes_form.html', {
        'job': job,
        'form': form_data,
        'note': note,
        'users': users,
        'action': 'update'
    })


def job_notes_view(request, job_id, note_id):
    """View a specific job note."""
    job = get_object_or_404(Job, id=job_id)
    note = get_object_or_404(JobNotes, id=note_id, job=job)
    
    # Get all users for assignment dropdown (designers only for notes)
    users = User.objects.filter(
        is_active=True,
        user_roles__role__type='DES',
        user_roles__is_active=True
    ).distinct().order_by('first_name', 'last_name')
    
    # Create form data for template
    form_data = {
        'note': note.note,
        'assigned_to': note.assigned_to_id,
        'follow_up': note.follow_up.strftime('%Y-%m-%dT%H:%M') if note.follow_up else '',
        'completed': note.completed
    }
    
    return render(request, 'job/job_notes_form.html', {
        'job': job,
        'form': form_data,
        'note': note,
        'users': users,
        'action': 'view'
    })


@require_POST
def set_primary_product_quote(request, job_id, quote_id):
    """Set a product quote as primary for a job."""
    from product.models import ProductQuote
    
    job = get_object_or_404(Job, id=job_id)
    quote = get_object_or_404(ProductQuote, id=quote_id, job=job)
    
    # First, unset any existing primary product quotes for this job
    ProductQuote.objects.filter(job=job, is_primary=True).update(is_primary=False)
    
    # Set this quote as primary
    quote.is_primary = True
    quote.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Product quote set as primary'})
    
    messages.success(request, 'Product quote set as primary.')
    return redirect('job:job_quotes', pk=job_id)


@require_POST
def set_primary_sitework_quote(request, job_id, quote_id):
    """Set a sitework quote as primary for a job."""
    from sitework.models import SiteworkQuote
    
    job = get_object_or_404(Job, id=job_id)
    quote = get_object_or_404(SiteworkQuote, id=quote_id, job=job)
    
    # First, unset any existing primary sitework quotes for this job
    SiteworkQuote.objects.filter(job=job, is_primary=True).update(is_primary=False)
    
    # Set this quote as primary
    quote.is_primary = True
    quote.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Sitework quote set as primary'})
    
    messages.success(request, 'Sitework quote set as primary.')
    return redirect('job:job_sitework', job_id=job_id)


@require_POST
def job_notes_edit(request, job_id, note_id):
    """Edit a job note via AJAX."""
    job = get_object_or_404(Job, id=job_id)
    note = get_object_or_404(JobNotes, id=note_id, job=job)
    
    # Get form data
    note_text = request.POST.get('note', '').strip()
    assigned_to_id = request.POST.get('assigned_to')
    follow_up_date = request.POST.get('follow_up')
    completed = request.POST.get('completed') == 'on'
    
    if not note_text:
        return JsonResponse({'success': False, 'error': 'Note content is required'})
    
    try:
        # Update the note
        note.note = note_text
        note.assigned_to_id = assigned_to_id if assigned_to_id else None
        note.follow_up = follow_up_date if follow_up_date else None
        note.completed = completed
        note.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def job_notes_delete(request, job_id, note_id):
    """Delete a job note."""
    job = get_object_or_404(Job, id=job_id)
    note = get_object_or_404(JobNotes, id=note_id, job=job)
    
    note.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Note deleted successfully.')
    return redirect('job:job_notes', job_id=job_id)


# ===== PRODUCT NOTES VIEWS =====

@require_POST
def add_product_note(request, job_id, quote_id, line_item_id):
    """Add or update a note for a specific product in a quote."""
    job = get_object_or_404(Job, id=job_id)
    quote = get_object_or_404(ProductQuote, id=quote_id, job=job)
    line_item = get_object_or_404(ProductQuoteLine, id=line_item_id, quote=quote)
    
    note_text = request.POST.get('note', '').strip()
    
    if not note_text:
        return JsonResponse({'success': False, 'error': 'Note content is required'})
    
    try:
        # Get or create the product note
        product_note, created = JobQuoteProductNotes.objects.get_or_create(
            job=job,
            line_item=line_item,
            defaults={
                'quote': quote,
                'note': note_text,
                'created_by': request.user if request.user.is_authenticated else None
            }
        )
        
        if not created:
            # Update existing note
            product_note.note = note_text
            product_note.modified_by = request.user if request.user.is_authenticated else None
            product_note.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Product note saved successfully',
            'note_id': product_note.id,
            'created': created
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def delete_product_note(request, job_id, note_id):
    """Delete a product note."""
    job = get_object_or_404(Job, id=job_id)
    note = get_object_or_404(JobQuoteProductNotes, id=note_id, job=job)
    
    note.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    messages.success(request, 'Product note deleted successfully.')
    return redirect('job:job_quote_products', job_id=job_id, quote_id=note.quote.id)


@require_POST
def update_product_note(request, job_id, note_id):
    """Update a product note via AJAX."""
    job = get_object_or_404(Job, id=job_id)
    note = get_object_or_404(JobQuoteProductNotes, id=note_id, job=job)
    
    note_text = request.POST.get('note', '').strip()
    
    if not note_text:
        return JsonResponse({'success': False, 'error': 'Note content is required'})
    
    try:
        note.note = note_text
        note.modified_by = request.user if request.user.is_authenticated else None
        note.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_POST
def delete_product_from_quote(request, job_id, quote_id, line_item_id):
    """Delete a product from a quote in the job context."""
    job = get_object_or_404(Job, id=job_id)
    quote = get_object_or_404(ProductQuote, id=quote_id, job=job)
    line_item = get_object_or_404(ProductQuoteLine, id=line_item_id, quote=quote)
    
    # Delete any associated product notes first
    JobQuoteProductNotes.objects.filter(job=job, line_item=line_item).delete()
    
    # Delete the line item
    line_item.delete()
    
    messages.success(request, 'Product removed from quote successfully.')
    return redirect('job:job_quote_products', job_id=job_id, quote_id=quote_id)


# ===== PURCHASE ORDER VIEWS =====

def job_purchase_orders(request, job_id):
    """View to list all purchase orders for a job."""
    job = get_object_or_404(Job, id=job_id)
    purchase_orders = (
        job.purchase_orders.all()
        .select_related('vendor', 'location')
        .annotate(
            subtotal_sum=Sum(
                F('items__quantity')
                * Coalesce(
                    F('items__cost'),
                    Value(0, output_field=DecimalField(max_digits=10, decimal_places=2)),
                ),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .order_by('vendor__vendor_name', '-created_at')
    )
    
    context = {
        'job': job,
        'purchase_orders': purchase_orders,
    }
    
    return render(request, 'job/job_purchase_orders.html', context)


@require_POST
@transaction.atomic
def sync_pos_from_primary_quote(request, job_id):
    """Sync products from the primary ProductQuote into Purchase Orders grouped by vendor.

    - Buckets quote lines by product.pref_vendor
    - For each vendor, finds or creates a draft PO for this job and merges items
    - Uses quote line unit_price as PO item unit cost
    """
    job = get_object_or_404(Job, id=job_id)

    from product.models import ProductQuote, ProductQuoteLine

    primary_quote = (
        ProductQuote.objects
        .filter(job=job, is_primary=True)
        .first()
    )

    if not primary_quote:
        messages.error(request, 'No primary product quote found for this job.')
        return redirect('job:job_purchase_orders', job_id=job.id)

    # Pull quote lines with product and vendor in one query
    quote_lines = (
        primary_quote.line_items
        .select_related('product', 'product__pref_vendor')
        .all()
    )

    # Bucket lines by vendor
    vendor_to_lines = {}
    skipped_count = 0
    for line in quote_lines:
        product = line.product
        vendor = getattr(product, 'pref_vendor', None)
        if not vendor:
            skipped_count += 1
            continue
        vendor_to_lines.setdefault(vendor, []).append(line)

    if not vendor_to_lines:
        messages.warning(request, 'No lines with vendor found to sync. Nothing changed.')
        return redirect('job:job_purchase_orders', job_id=job.id)

    # Fetch existing draft POs for these vendors
    vendor_ids = [v.id for v in vendor_to_lines.keys()]
    existing_pos = (
        PurchaseOrder.objects
        .filter(job=job, vendor_id__in=vendor_ids, status='draft')
        .select_related('vendor')
    )
    vendor_id_to_po = {po.vendor_id: po for po in existing_pos}

    # Get or create default "Others" store for location
    from .models import Store
    default_store, _ = Store.objects.get_or_create(
        store_name='Others',
        defaults={'status': 'A'}
    )

    # Ensure a PO per vendor (draft)
    created_pos = []
    for vendor in vendor_to_lines.keys():
        if vendor.id not in vendor_id_to_po:
            po = PurchaseOrder(
                job=job,
                vendor=vendor,
                status='draft',
                location=default_store,  # default; user can edit later
                arrive_by_date=timezone.now().date(),
                created_by=request.user if request.user.is_authenticated else None,
            )
            po.save()
            vendor_id_to_po[vendor.id] = po
            created_pos.append(po)

    # Merge items per vendor
    today = timezone.now().date()
    for vendor, lines in vendor_to_lines.items():
        po = vendor_id_to_po[vendor.id]

        # Build a map of existing items by part_number for quick merge
        existing_items = {i.part_number: i for i in po.items.all()}

        for line in lines:
            product = line.product
            part_number = product.part_no
            description = line.product_description or product.description
            quantity = line.quantity
            unit_cost = line.unit_price

            if part_number in existing_items:
                item = existing_items[part_number]
                # Increase quantity and optionally refresh cost/description
                item.quantity += quantity
                if unit_cost is not None:
                    item.cost = unit_cost
                if description and not item.description:
                    item.description = description
                if not item.ordered_date:
                    item.ordered_date = today
                item.save()
            else:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    part_number=part_number,
                    description=description,
                    ordered_date=today,
                    quantity=quantity,
                    confirmed=False,
                    received_quantity=0,
                    sent_to_job_quantity=0,
                    cost=unit_cost,
                )

    added_vendor_count = len(vendor_to_lines)
    if skipped_count:
        messages.warning(request, f'Sync complete. {added_vendor_count} vendor groups processed. {skipped_count} lines skipped (no vendor).')
    else:
        messages.success(request, f'Sync complete. {added_vendor_count} vendor groups processed.')

    return redirect('job:job_purchase_orders', job_id=job.id)


def job_purchase_order_create(request, job_id):
    """Create a new purchase order for a job."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, job=job)
        if form.is_valid():
            purchase_order = form.save(commit=False)
            purchase_order.job = job
            purchase_order.created_by = request.user if request.user.is_authenticated else None
            purchase_order.save()
            
            messages.success(request, 'Purchase order created successfully.')
            return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=purchase_order.id)
    else:
        form = PurchaseOrderForm(job=job)
    
    context = {
        'job': job,
        'form': form,
        'action': 'create'
    }
    
    return render(request, 'job/job_purchase_order_form.html', context)


def job_purchase_order_detail(request, job_id, po_id):
    """View a specific purchase order for a job."""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    
    # Get all items for this PO
    items = purchase_order.items.all().order_by('ordered_date', 'part_number')
    
    context = {
        'job': job,
        'purchase_order': purchase_order,
        'items': items,
    }
    
    return render(request, 'job/job_purchase_order_detail.html', context)


def job_purchase_order_edit(request, job_id, po_id):
    """Edit an existing purchase order for a job."""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=purchase_order, job=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Purchase order updated successfully.')
            return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=purchase_order.id)
    else:
        form = PurchaseOrderForm(instance=purchase_order, job=job)
    
    context = {
        'job': job,
        'purchase_order': purchase_order,
        'form': form,
        'action': 'edit'
    }
    
    return render(request, 'job/job_purchase_order_form.html', context)


def job_purchase_order_item_add(request, job_id, po_id):
    """Add a new item to a purchase order."""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    
    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST, purchase_order=purchase_order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item added to purchase order successfully.')
            return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=purchase_order.id)
    else:
        form = PurchaseOrderItemForm(purchase_order=purchase_order)
    
    # Get existing items for the PO
    items = purchase_order.items.all().order_by('-created_at')
    
    context = {
        'job': job,
        'purchase_order': purchase_order,
        'form': form,
        'items': items,
        'action': 'add_item'
    }
    
    return render(request, 'job/job_purchase_order_item_form.html', context)


def job_purchase_order_item_edit(request, job_id, po_id, item_id):
    """Edit an existing item in a purchase order."""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    item = get_object_or_404(PurchaseOrderItem, id=item_id, purchase_order=purchase_order)
    
    if request.method == 'POST':
        form = PurchaseOrderItemForm(request.POST, instance=item, purchase_order=purchase_order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item updated successfully.')
            return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=purchase_order.id)
    else:
        form = PurchaseOrderItemForm(instance=item, purchase_order=purchase_order)
    
    # Get existing items for the PO
    items = purchase_order.items.all().order_by('-created_at')
    
    context = {
        'job': job,
        'purchase_order': purchase_order,
        'item': item,
        'form': form,
        'items': items,
        'action': 'edit_item'
    }
    
    return render(request, 'job/job_purchase_order_item_form.html', context)


@require_POST
def job_purchase_order_item_toggle_confirm(request, job_id, po_id, item_id):
    """Toggle the confirmed flag for a PO item and return to PO detail."""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    item = get_object_or_404(PurchaseOrderItem, id=item_id, purchase_order=purchase_order)

    item.confirmed = not item.confirmed
    item.save(update_fields=['confirmed', 'updated_at'])

    return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=po_id)


def job_purchase_orders_export_confirmed(request, job_id):
    """Render a page listing all confirmed PO items across the job's POs."""
    job = get_object_or_404(Job, id=job_id)

    # Fetch confirmed items across all POs for this job
    confirmed_items = (
        PurchaseOrderItem.objects
        .filter(purchase_order__job=job, confirmed=True)
        .select_related('purchase_order', 'purchase_order__vendor')
        .order_by('purchase_order__vendor__vendor_name', 'purchase_order__po_number', 'part_number')
    )

    context = {
        'job': job,
        'confirmed_items': confirmed_items,
    }

    return render(request, 'job/job_purchase_orders_export_confirmed.html', context)


@require_POST
def job_purchase_order_item_delete(request, job_id, po_id, item_id):
    """Delete an item from a purchase order."""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    item = get_object_or_404(PurchaseOrderItem, id=item_id, purchase_order=purchase_order)
    
    item.delete()
    messages.success(request, 'Item removed from purchase order successfully.')
    
    return redirect('job:job_purchase_order_detail', job_id=job_id, po_id=purchase_order.id)


@require_POST
def job_purchase_order_delete(request, job_id, po_id):
    """Delete a purchase order."""
    job = get_object_or_404(Job, id=job_id)
    purchase_order = get_object_or_404(PurchaseOrder, id=po_id, job=job)
    
    purchase_order.delete()
    messages.success(request, 'Purchase order deleted successfully.')
    
    return redirect('job:job_purchase_orders', job_id=job_id)


# ===== VENDOR VIEWS =====

def vendor_list(request):
    """List all vendors."""
    vendors = Vendor.objects.all().order_by('vendor_name')
    
    context = {
        'vendors': vendors,
    }
    
    return render(request, 'job/vendor_list.html', context)


def vendor_create(request):
    """Create a new vendor."""
    if request.method == 'POST':
        form = VendorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vendor created successfully.')
            return redirect('job:vendor_list')
    else:
        form = VendorForm()
    
    context = {
        'form': form,
        'action': 'create'
    }
    
    return render(request, 'job/vendor_form.html', context)


def vendor_edit(request, vendor_id):
    """Edit an existing vendor."""
    vendor = get_object_or_404(Vendor, id=vendor_id)
    
    if request.method == 'POST':
        form = VendorForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vendor updated successfully.')
            return redirect('job:vendor_list')
    else:
        form = VendorForm(instance=vendor)
    
    context = {
        'vendor': vendor,
        'form': form,
        'action': 'edit'
    }
    
    return render(request, 'job/vendor_form.html', context)


@require_POST
def vendor_delete(request, vendor_id):
    """Delete a vendor."""
    vendor = get_object_or_404(Vendor, id=vendor_id)
    vendor.delete()
    messages.success(request, 'Vendor deleted successfully.')
    
    return redirect('job:vendor_list')


@login_required
def sales_list(request):
    """Display list of all sales and change orders"""
    from decimal import Decimal
    from datetime import date
    
    # Get filter parameters from request
    type_filter = request.GET.get('type', 'all')  # 'all', 'sale', 'change_order'
    user_filter = request.GET.get('user', 'all')  # 'all' or user ID
    start_date = request.GET.get('start_date', '')  # Start date filter
    end_date = request.GET.get('end_date', '')  # End date filter
    search_query = request.GET.get('search', '').strip()  # Job code search
    
    # Get all sales with related data
    sales = Sale.objects.select_related('job', 'job__customer', 'job__soldby', 'product_code', 'created_by').order_by('-sale_date', '-created_at')
    
    # Get all change orders with related data
    change_orders = ChangeOrder.objects.select_related('job', 'job__customer', 'job__soldby', 'product_code', 'created_by').order_by('-order_date', '-created_at')
        
    # Get all users, excluding specific users, ordered by first_name, last_name, or username as fallback
    excluded_usernames = ['bill', 'billy', 'txin214', 'admin', 'myname']
    all_users = User.objects.exclude(
        username__in=excluded_usernames
    ).exclude(
        Q(first_name__iexact='mu') & Q(last_name__iexact='name')
    ).order_by('first_name', 'last_name', 'username')
    
    # Parse date filters
    start_date_obj = None
    end_date_obj = None
    if start_date:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    if end_date:
        try:
            from datetime import datetime
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            pass
                
    # Combine sales and change orders into a single list with type indicator
    combined_list = []
    
    # Add sales to combined list (only if filter allows)
    if type_filter in ['all', 'sale']:
        for sale in sales:
            sales_person = sale.created_by if sale.created_by else sale.job.soldby
            sale_date_obj = sale.sale_date or sale.created_at.date() if sale.created_at else date.today()
            
            # Filter by user if specified
            user_match = user_filter == 'all' or (user_filter and sales_person and str(sales_person.id) == user_filter)
            
            # Filter by date range if specified
            date_match = True
            if start_date_obj and sale_date_obj < start_date_obj:
                date_match = False
            if end_date_obj and sale_date_obj > end_date_obj:
                date_match = False
            
            # Filter by job code search if specified
            job_code_match = True
            if search_query:
                job_code = sale.job.job_code or ''
                if search_query.lower() not in job_code.lower():
                    job_code_match = False
            
            if user_match and date_match and job_code_match:
                combined_list.append({
                    'type': 'Sale',
                    'obj': sale,
                    'date': sale_date_obj,
                    'job': sale.job,
                    'customer': sale.job.customer,
                    'sales_person': sales_person,
                    'amount': sale.sale_amount,
                    'product_code': sale.product_code,
                    'description': sale.comment or (sale.product_code.description if sale.product_code else ''),
                })
    
    # Add change orders to combined list (only if filter allows)
    if type_filter in ['all', 'change_order']:
        for change_order in change_orders:
            sales_person = change_order.created_by if change_order.created_by else change_order.job.soldby
            change_order_date = change_order.order_date
            
            # Filter by user if specified
            user_match = user_filter == 'all' or (user_filter and sales_person and str(sales_person.id) == user_filter)
            
            # Filter by date range if specified
            date_match = True
            if start_date_obj and change_order_date < start_date_obj:
                date_match = False
            if end_date_obj and change_order_date > end_date_obj:
                date_match = False
            
            # Filter by job code search if specified
            job_code_match = True
            if search_query:
                job_code = change_order.job.job_code or ''
                if search_query.lower() not in job_code.lower():
                    job_code_match = False
            
            if user_match and date_match and job_code_match:
                combined_list.append({
                    'type': 'Change Order',
                    'obj': change_order,
                    'date': change_order_date,
                    'job': change_order.job,
                    'customer': change_order.job.customer,
                    'sales_person': sales_person,
                    'amount': change_order.amount or Decimal('0'),
                    'product_code': change_order.product_code,
                    'description': change_order.description,
                })
    
    # Sort by date (newest first)
    combined_list.sort(key=lambda x: x['date'], reverse=True)
    
    # Pagination
    paginator = Paginator(combined_list, 16)  # 16 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get total count
    total_items = len(combined_list)
    
    context = {
        'items': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_items': total_items,
        'type_filter': type_filter,
        'user_filter': user_filter,
        'users': all_users,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
    }
    
    return render(request, 'job/sales_list.html', context)


@login_required
def batch_entry_sales(request):
    """Create Sale rows from Batch Entry > Sales."""
    from datetime import date
    from decimal import Decimal, InvalidOperation
    from product.models import ProductCode

    allowed_codes = [
        'CK', 'PSD', 'FL', 'CR', 'LV', 'PFX', 'WP', 'MX', 'AP', 'SL',
        'SLW', 'CTS', 'SS', 'PFF', 'DEL', 'DS', 'BA', 'HD', 'DIS', 'CTQ'
    ]
    product_codes = ProductCode.objects.filter(code__in=allowed_codes).order_by('code')

    if request.method == 'POST':
        job_id = request.POST.get('job_id')
        product_code_id = request.POST.get('product_code_id')
        sale_date_raw = request.POST.get('sale_date')
        tax = request.POST.get('tax', 'UT')
        comment = (request.POST.get('comment') or '').strip()
        sale_amount_raw = request.POST.get('sale_amount')

        if not job_id:
            messages.error(request, 'Select a job code from the search results.')
        elif not product_code_id:
            messages.error(request, 'Select a product code.')
        elif not sale_amount_raw:
            messages.error(request, 'Enter a sale amount.')
        else:
            job = Job.objects.filter(pk=job_id).first()
            if not job:
                messages.error(request, 'Selected job no longer exists.')
            else:
                try:
                    sale_amount = Decimal(str(sale_amount_raw))
                except (InvalidOperation, TypeError, ValueError):
                    sale_amount = None
                if sale_amount is None:
                    messages.error(request, 'Sale amount is invalid.')
                else:
                    try:
                        from datetime import datetime
                        parsed_date = (
                            datetime.strptime(sale_date_raw, '%Y-%m-%d').date()
                            if sale_date_raw else date.today()
                        )
                    except ValueError:
                        parsed_date = date.today()

                    Sale.objects.create(
                        job=job,
                        product_code_id=product_code_id,
                        sale_amount=sale_amount,
                        sale_date=parsed_date,
                        tax=tax if tax in {'EX', 'ST', 'UT', 'LB', 'SU'} else 'UT',
                        comment=comment,
                        created_by=request.user if request.user.is_authenticated else None,
                    )
                    messages.success(request, f'Sale created for {job.job_code}.')
                    return redirect('job:batch_entry_sales')

    context = {
        'batch_type': 'sales',
        'page_title': 'Batch Entry - Sales',
        'submit_label': 'Create Sale',
        'product_codes': product_codes,
        'initial_date': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'job/batch_entry_form.html', context)


@login_required
def batch_entry_receipts(request):
    """Create Payment rows from Batch Entry > Receipts."""
    from datetime import date
    from decimal import Decimal, InvalidOperation
    from .models import Payment, AccountCategory

    account_categories = AccountCategory.objects.filter(status='A').order_by('code')

    if request.method == 'POST':
        job_id = request.POST.get('job_id')
        account_category_id = request.POST.get('account_category_id') or None
        date_raw = request.POST.get('date')
        discount_raw = request.POST.get('discount')
        comment = (request.POST.get('comment') or '').strip()
        amount_raw = request.POST.get('amount')

        if not job_id:
            messages.error(request, 'Select a job code from the search results.')
        elif not amount_raw:
            messages.error(request, 'Enter an amount.')
        else:
            job = Job.objects.filter(pk=job_id).first()
            if not job:
                messages.error(request, 'Selected job no longer exists.')
            else:
                try:
                    amount = Decimal(str(amount_raw))
                except (InvalidOperation, TypeError, ValueError):
                    amount = None
                try:
                    discount = Decimal(str(discount_raw)) if discount_raw not in (None, '') else Decimal('0')
                except (InvalidOperation, TypeError, ValueError):
                    discount = None

                if amount is None:
                    messages.error(request, 'Amount is invalid.')
                elif discount is None:
                    messages.error(request, 'Discount is invalid.')
                else:
                    try:
                        from datetime import datetime
                        parsed_date = (
                            datetime.strptime(date_raw, '%Y-%m-%d').date()
                            if date_raw else date.today()
                        )
                    except ValueError:
                        parsed_date = date.today()

                    Payment.objects.create(
                        job=job,
                        date=parsed_date,
                        account_category_id=account_category_id,
                        discount=discount,
                        comment=comment,
                        amount=amount,
                        by=request.user if request.user.is_authenticated else None,
                    )
                    messages.success(request, f'Receipt created for {job.job_code}.')
                    return redirect('job:batch_entry_receipts')

    context = {
        'batch_type': 'receipts',
        'page_title': 'Batch Entry - Receipts',
        'submit_label': 'Create Receipt',
        'account_categories': account_categories,
        'initial_date': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'job/batch_entry_form.html', context)


@login_required
def batch_entry_change_orders(request):
    """Create ChangeOrder rows from Batch Entry > Change Orders."""
    from datetime import date
    from decimal import Decimal, InvalidOperation
    from django.core.exceptions import ValidationError
    from product.models import ProductCode

    allowed_codes = [
        'CK', 'PSD', 'FL', 'CR', 'LV', 'PFX', 'WP', 'MX', 'AP', 'SL',
        'SLW', 'CTS', 'SS', 'PFF', 'DEL', 'DS', 'BA', 'HD', 'DIS', 'CTQ'
    ]
    product_codes = ProductCode.objects.filter(code__in=allowed_codes).order_by('code')

    if request.method == 'POST':
        job_id = request.POST.get('job_id')
        product_code_id = request.POST.get('product_code_id') or None
        order_date_raw = request.POST.get('order_date')
        tax = request.POST.get('tax') or 'UT'
        description = (request.POST.get('description') or '').strip()
        amount_raw = request.POST.get('amount')

        if not job_id:
            messages.error(request, 'Select a job code from the search results.')
        elif not description:
            messages.error(request, 'Description is required.')
        else:
            job = Job.objects.filter(pk=job_id).first()
            if not job:
                messages.error(request, 'Selected job no longer exists.')
            else:
                amount = None
                if amount_raw not in (None, ''):
                    try:
                        amount = Decimal(str(amount_raw))
                    except (InvalidOperation, TypeError, ValueError):
                        messages.error(request, 'Amount is invalid.')
                        amount = 'invalid'
                if amount != 'invalid':
                    try:
                        from datetime import datetime
                        parsed_date = (
                            datetime.strptime(order_date_raw, '%Y-%m-%d').date()
                            if order_date_raw else date.today()
                        )
                    except ValueError:
                        parsed_date = date.today()

                    change_order = ChangeOrder(
                        job=job,
                        product_code_id=product_code_id,
                        description=description,
                        amount=amount,
                        order_date=parsed_date,
                        tax=tax if tax in {'EX', 'ST', 'UT', 'LB', 'SU'} else 'UT',
                        created_by=request.user if request.user.is_authenticated else None,
                    )
                    try:
                        change_order.save()
                        messages.success(request, f'Change order created for {job.job_code}.')
                        return redirect('job:batch_entry_change_orders')
                    except ValidationError as exc:
                        messages.error(request, str(exc))

    context = {
        'batch_type': 'change_orders',
        'page_title': 'Batch Entry - Change Orders',
        'submit_label': 'Create Change Order',
        'product_codes': product_codes,
        'initial_date': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'job/batch_entry_form.html', context)


@login_required
def sales_by_person(request):
    """Sales and change orders by person, aggregated per job (one row per user per job)."""
    from decimal import Decimal
    from datetime import date
    from collections import defaultdict

    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    start_date_obj = None
    end_date_obj = None
    if start_date:
        try:
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    if end_date:
        try:
            from datetime import datetime
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            pass

    sales = Sale.objects.select_related('job', 'job__customer', 'job__soldby', 'created_by').order_by('-sale_date', '-created_at')
    change_orders = ChangeOrder.objects.select_related('job', 'job__customer', 'job__soldby', 'created_by').order_by('-order_date', '-created_at')

    # user_id -> { user, job_id -> per-job aggregates }
    grouped_by_user = defaultdict(lambda: {
        'user': None,
        'by_job': {},
    })

    def job_slot():
        return {
            'job': None,
            'customer': None,
            'total_sales': Decimal('0'),
            'total_change_orders': Decimal('0'),
            'last_activity': None,
        }

    # Process sales -> aggregate (user, job)
    for sale in sales:
        sales_person = sale.created_by if sale.created_by else sale.job.soldby
        sale_date_obj = sale.sale_date or (sale.created_at.date() if sale.created_at else date.today())

        date_match = True
        if start_date_obj and sale_date_obj < start_date_obj:
            date_match = False
        if end_date_obj and sale_date_obj > end_date_obj:
            date_match = False

        if not date_match or not sales_person:
            continue

        user_key = sales_person.id
        if grouped_by_user[user_key]['user'] is None:
            grouped_by_user[user_key]['user'] = sales_person

        jid = sale.job_id
        if jid not in grouped_by_user[user_key]['by_job']:
            grouped_by_user[user_key]['by_job'][jid] = job_slot()
        slot = grouped_by_user[user_key]['by_job'][jid]
        if slot['job'] is None:
            slot['job'] = sale.job
            slot['customer'] = sale.job.customer

        amt = sale.sale_amount or Decimal('0')
        slot['total_sales'] += amt
        if slot['last_activity'] is None or sale_date_obj > slot['last_activity']:
            slot['last_activity'] = sale_date_obj

    # Process change orders -> same buckets
    for change_order in change_orders:
        sales_person = change_order.created_by if change_order.created_by else change_order.job.soldby
        change_order_date = change_order.order_date

        date_match = True
        if start_date_obj and change_order_date < start_date_obj:
            date_match = False
        if end_date_obj and change_order_date > end_date_obj:
            date_match = False

        if not date_match or not sales_person:
            continue

        user_key = sales_person.id
        if grouped_by_user[user_key]['user'] is None:
            grouped_by_user[user_key]['user'] = sales_person

        jid = change_order.job_id
        if jid not in grouped_by_user[user_key]['by_job']:
            grouped_by_user[user_key]['by_job'][jid] = job_slot()
        slot = grouped_by_user[user_key]['by_job'][jid]
        if slot['job'] is None:
            slot['job'] = change_order.job
            slot['customer'] = change_order.job.customer

        amount = change_order.amount or Decimal('0')
        slot['total_change_orders'] += amount
        if slot['last_activity'] is None or change_order_date > slot['last_activity']:
            slot['last_activity'] = change_order_date

    grouped_list = []
    for user_key, group_data in grouped_by_user.items():
        if not group_data['user']:
            continue
        job_rows = []
        for _jid, jdata in group_data['by_job'].items():
            jdata['grand_total'] = jdata['total_sales'] + jdata['total_change_orders']
            job_rows.append(jdata)
        job_rows.sort(key=lambda x: ((x['job'].job_code or '').lower(), x['job'].pk))

        total_sales = sum(j['total_sales'] for j in job_rows)
        total_change_orders = sum(j['total_change_orders'] for j in job_rows)
        grouped_list.append({
            'user': group_data['user'],
            'job_rows': job_rows,
            'total_sales': total_sales,
            'total_change_orders': total_change_orders,
            'grand_total': total_sales + total_change_orders,
        })

    grouped_list.sort(key=lambda x: (
        x['user'].first_name or '',
        x['user'].last_name or '',
        x['user'].username or ''
    ))

    total_sales_all = sum(g['total_sales'] for g in grouped_list)
    total_change_orders_all = sum(g['total_change_orders'] for g in grouped_list)
    grand_total_all = total_sales_all + total_change_orders_all

    context = {
        'grouped_by_user': grouped_list,
        'total_sales_all': total_sales_all,
        'total_change_orders_all': total_change_orders_all,
        'grand_total_all': grand_total_all,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'job/sales_by_person.html', context)


# ============== Change Order Views ==============

def job_change_orders(request, job_id):
    """Display change orders list for a job"""
    job = get_object_or_404(Job, pk=job_id)
    change_orders = job.change_orders.all().select_related('created_by').order_by('-order_date', '-created_at')
    
    # Calculate total change order amount (only include change orders with amounts)
    from decimal import Decimal
    total_change_amount = sum(co.amount for co in change_orders if co.amount is not None) if change_orders else Decimal('0.00')
    
    context = {
        'job': job,
        'change_orders': change_orders,
        'total_change_amount': total_change_amount,
        'is_sold': job.sold,
    }
    
    return render(request, 'job/job_change_orders.html', context)


def job_change_order_create(request, job_id):
    """Create a new change order for a job"""
    from .forms import ChangeOrderForm
    job = get_object_or_404(Job, pk=job_id)
    
    # Check if job is sold
    if not job.sold:
        messages.error(request, 'Cannot create change order for a job that is not sold.')
        return redirect('job:job_detail', pk=job_id)
    
    if request.method == 'POST':
        form = ChangeOrderForm(request.POST)
        if form.is_valid():
            change_order = form.save(commit=False)
            change_order.job = job
            # Set created_by to current user if authenticated, otherwise None
            change_order.created_by = request.user if request.user.is_authenticated else None
            try:
                change_order.save()
                messages.success(request, 'Change order created successfully.')
                return redirect('job:job_change_orders', job_id=job.id)
            except Exception as e:
                messages.error(request, f'Error creating change order: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ChangeOrderForm()
    
    context = {
        'job': job,
        'form': form,
        'is_edit': False,
    }
    
    return render(request, 'job/job_change_order_form.html', context)


def job_change_order_edit(request, job_id, change_order_id):
    """Edit an existing change order"""
    from .forms import ChangeOrderForm
    job = get_object_or_404(Job, pk=job_id)
    change_order = get_object_or_404(ChangeOrder, pk=change_order_id, job=job)
    
    if request.method == 'POST':
        form = ChangeOrderForm(request.POST, instance=change_order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Change order updated successfully.')
            return redirect('job:job_change_orders', job_id=job.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ChangeOrderForm(instance=change_order)
    
    context = {
        'job': job,
        'form': form,
        'change_order': change_order,
        'is_edit': True,
    }
    
    return render(request, 'job/job_change_order_form.html', context)


@require_POST
def job_change_order_delete(request, job_id, change_order_id):
    """Delete a change order"""
    job = get_object_or_404(Job, pk=job_id)
    change_order = get_object_or_404(ChangeOrder, pk=change_order_id, job=job)
    
    change_order.delete()
    messages.success(request, 'Change order deleted successfully.')
    
    return redirect('job:job_change_orders', job_id=job.id)


def job_change_orders_pdf(request, job_id):
    """Generate PDF for change orders list"""
    from job.pdf_generator import change_orders_pdf_generate
    return change_orders_pdf_generate(request, job_id)


def job_payments(request, job_id):
    """Display payments list for a job"""
    job = get_object_or_404(Job, pk=job_id)
    payments = job.payments.all().select_related('account_category', 'by').order_by('-date', '-created_at')
    
    # Calculate total payment amount
    from decimal import Decimal
    total_payment_amount = sum(p.amount for p in payments) if payments else Decimal('0.00')
    total_discount = sum(p.discount for p in payments) if payments else Decimal('0.00')
    total = total_payment_amount - total_discount
    
    context = {
        'job': job,
        'payments': payments,
        'total_payment_amount': total_payment_amount,
        'total_discount': total_discount,
        'total': total,
    }
    
    return render(request, 'job/job_payments.html', context)


def job_payment_create(request, job_id):
    """Create a new payment for a job"""
    from .forms import PaymentForm
    from .models import Payment
    job = get_object_or_404(Job, pk=job_id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.job = job
            # Set 'by' to current user if authenticated, otherwise None
            payment.by = request.user if request.user.is_authenticated else None
            try:
                payment.save()
                messages.success(request, 'Payment created successfully.')
                return redirect('job:job_payments', job_id=job.id)
            except Exception as e:
                messages.error(request, f'Error creating payment: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm()
    
    context = {
        'job': job,
        'form': form,
        'is_edit': False,
    }
    
    return render(request, 'job/job_payment_form.html', context)


def job_payment_edit(request, job_id, payment_id):
    """Edit an existing payment"""
    from .forms import PaymentForm
    from .models import Payment
    job = get_object_or_404(Job, pk=job_id)
    payment = get_object_or_404(Payment, pk=payment_id, job=job)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Payment updated successfully.')
            return redirect('job:job_payments', job_id=job.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm(instance=payment)
    
    context = {
        'job': job,
        'form': form,
        'payment': payment,
        'is_edit': True,
    }
    
    return render(request, 'job/job_payment_form.html', context)


@require_POST
def job_payment_delete(request, job_id, payment_id):
    """Delete a payment"""
    from .models import Payment
    job = get_object_or_404(Job, pk=job_id)
    payment = get_object_or_404(Payment, pk=payment_id, job=job)
    
    payment.delete()
    messages.success(request, 'Payment deleted successfully.')
    
    return redirect('job:job_payments', job_id=job.id)


def job_payment_lien_waiver_pdf(request, job_id, payment_id):
    """Generate lien waiver PDF for a payment"""
    from job.pdf_generator import lien_waiver_pdf_generate
    return lien_waiver_pdf_generate(request, job_id, payment_id)


def job_accounting(request, job_id):
    """Display combined sales and change orders for accounting view"""
    from collections import OrderedDict
    from decimal import Decimal
    from datetime import date
    
    job = get_object_or_404(Job, pk=job_id)

    # Backfill sales + SLW milestones if job was sold before sync ran.
    if job.sold:
        from .sales_from_quote import sync_sales_when_job_sold
        sync_sales_when_job_sold(
            job,
            request.user if request.user.is_authenticated else None,
        )
    
    # Individual sales/change orders for accounting tables (chronological)
    sales = job.sales.all().select_related('product_code', 'created_by').order_by('sale_date', 'created_at')
    change_orders = job.change_orders.all().select_related('product_code', 'created_by').order_by('order_date', 'created_at')

    total_sales_amount = sum((s.sale_amount or Decimal('0.00')) for s in sales)
    total_sales_tax = sum((s.tax_amount or Decimal('0.00')) for s in sales)

    billing_lines = []
    for sale in sales:
        billing_lines.append({
            'date': sale.sale_date,
            'product_code': sale.product_code.code if sale.product_code else '',
            'tax': sale.get_tax_display() if sale.tax else '',
            'comment': sale.comment or (sale.product_code.description if sale.product_code else ''),
            'by': sale.created_by,
            'amount': sale.sale_amount,
            'edit_url_name': 'job:job_sale_edit',
            'edit_id': sale.id,
        })
    for change_order in change_orders:
        billing_lines.append({
            'date': change_order.order_date,
            'product_code': change_order.product_code.code if change_order.product_code else '',
            'tax': change_order.get_tax_display() if change_order.tax else '',
            'comment': change_order.description,
            'by': change_order.created_by,
            'amount': change_order.amount,
            'edit_url_name': 'job:job_change_order_edit',
            'edit_id': change_order.id,
        })
    billing_lines.sort(key=lambda row: (row['date'] or date.min, row['product_code'] or ''))
    total_billing_tax = total_sales_tax
    
    # Calculate total change order amount (only include change orders with amounts)
    total_change_amount = sum(co.amount for co in change_orders if co.amount is not None) if change_orders else Decimal('0.00')
    
    # Get payments data
    payments = job.payments.all().select_related('account_category', 'by').order_by('date', 'created_at')
    
    # Calculate payment totals
    total_payment_amount = sum(p.amount for p in payments) if payments else Decimal('0.00')
    total_discount = sum(p.discount for p in payments) if payments else Decimal('0.00')
    payment_total = total_payment_amount - total_discount
    
    # Calculate grand total (sales + change orders)
    grand_total = total_sales_amount + total_change_amount
    
    # Calculate Due Now (grand total - payment total)
    due_now = grand_total - payment_total

    # Build accounting timeline datasets for charts (ordered by transaction date).
    timeline = OrderedDict()

    def _ensure_day(day):
        if day not in timeline:
            timeline[day] = {
                'sales': Decimal('0.00'),
                'change_orders': Decimal('0.00'),
                'payments': Decimal('0.00'),
            }

    for sale in sales:
        day = sale.sale_date or (sale.created_at.date() if sale.created_at else date.today())
        _ensure_day(day)
        timeline[day]['sales'] += (sale.sale_amount or Decimal('0.00'))

    for co in change_orders:
        day = co.order_date or (co.created_at.date() if co.created_at else date.today())
        _ensure_day(day)
        timeline[day]['change_orders'] += (co.amount or Decimal('0.00'))

    for payment in payments:
        day = payment.date or (payment.created_at.date() if payment.created_at else date.today())
        _ensure_day(day)
        # Payment total uses amount minus discount; mirror that in chart impact.
        timeline[day]['payments'] += (payment.amount or Decimal('0.00')) - (payment.discount or Decimal('0.00'))

    chart_labels = []
    chart_sales = []
    chart_change_orders = []
    chart_payments = []
    chart_running_balance = []
    running_balance = Decimal('0.00')
    for day in sorted(timeline.keys()):
        day_data = timeline[day]
        day_sales = day_data['sales']
        day_change = day_data['change_orders']
        day_payments = day_data['payments']
        running_balance += day_sales + day_change - day_payments

        chart_labels.append(day.strftime('%Y-%m-%d'))
        chart_sales.append(float(day_sales))
        chart_change_orders.append(float(day_change))
        chart_payments.append(float(day_payments))
        chart_running_balance.append(float(running_balance))
    
    context = {
        'job': job,
        'sales': sales,
        'total_sales_amount': total_sales_amount,
        'total_sales_tax': total_sales_tax,
        'change_orders': change_orders,
        'total_change_amount': total_change_amount,
        'billing_lines': billing_lines,
        'total_billing_tax': total_billing_tax,
        'grand_total': grand_total,
        'payments': payments,
        'total_payment_amount': total_payment_amount,
        'total_discount': total_discount,
        'payment_total': payment_total,
        'due_now': due_now,
        'chart_labels': chart_labels,
        'chart_sales': chart_sales,
        'chart_change_orders': chart_change_orders,
        'chart_payments': chart_payments,
        'chart_running_balance': chart_running_balance,
        'has_chart_data': bool(chart_labels),
    }
    
    return render(request, 'job/job_accounting.html', context)


# ============== Job Sales Views ==============

@login_required
def job_sales(request, job_id):
    """Display sales list for a job"""
    from collections import defaultdict
    from decimal import Decimal
    from datetime import date
    
    job = get_object_or_404(Job, pk=job_id)

    if job.sold:
        from .sales_from_quote import sync_sales_when_job_sold
        sync_sales_when_job_sold(
            job,
            request.user if request.user.is_authenticated else None,
        )

    sales = job.sales.all().select_related('product_code', 'created_by').order_by('-sale_date', '-created_at')
    
    # Group sales by product_code
    grouped_sales = defaultdict(lambda: {
        'sales': [],
        'total': Decimal('0.00'),
        'total_cost': Decimal('0.00'),
        'total_tax': Decimal('0.00'),
        'product_code': None,
        'tax': None,
        'sale_date': None,
    })
    for sale in sales:
        product_code_id = sale.product_code_id if sale.product_code else None
        product_code_key = product_code_id if product_code_id else 'no_code'
        
        if grouped_sales[product_code_key]['product_code'] is None:
            grouped_sales[product_code_key]['product_code'] = sale.product_code
            grouped_sales[product_code_key]['tax'] = sale.tax
            grouped_sales[product_code_key]['sale_date'] = sale.sale_date
        
        grouped_sales[product_code_key]['sales'].append(sale)
        grouped_sales[product_code_key]['total'] += sale.sale_amount
        if sale.cost_amount is not None:
            grouped_sales[product_code_key]['total_cost'] += sale.cost_amount
        if sale.tax_amount is not None:
            grouped_sales[product_code_key]['total_tax'] += sale.tax_amount
    
    # Convert to list sorted by product code
    grouped_sales_list = []
    for key, group_data in grouped_sales.items():
        grouped_sales_list.append({
            'product_code': group_data['product_code'],
            'product_code_id': key if key != 'no_code' else None,
            'tax': group_data['tax'],
            'sale_date': group_data['sale_date'],
            'total': group_data['total'],
            'total_cost': group_data['total_cost'],
            'total_tax': group_data['total_tax'],
            'sales': group_data['sales'],
            'count': len(group_data['sales'])
        })
    
    # Sort by product code (None/empty last)
    grouped_sales_list.sort(key=lambda x: (x['product_code'].code if x['product_code'] else 'zzz', x['sale_date'] or date.min), reverse=True)
    
    # Calculate totals
    total_sales_amount = sum(group['total'] for group in grouped_sales_list)
    total_sales_cost = sum(group['total_cost'] for group in grouped_sales_list)
    total_sales_tax = sum(group['total_tax'] for group in grouped_sales_list)
    
    # Get main quote (primary product quote) and group products by category
    # Only fetch quote data if job is sold
    main_quote = None
    grouped_products = None
    tax_rate = Decimal('0')
    quote_tax = Decimal('0')
    quote_total = Decimal('0')
    sitework_total = Decimal('0')
    sitework_subtotal = Decimal('0')
    sitework_tax = Decimal('0')
    sl_product_code = None
    product_codes = []
    
    if job.sold:
        try:
            main_quote = job.product_quotes.filter(is_primary=True).select_related().prefetch_related(
                'line_items__product__category',
                'line_items__product__sub_category1',
                'adhoc_line_items'
            ).first()
            if main_quote:
                from product.utils import group_quote_line_items
                from .models import CategoryProductCodeMap, SubCategory1ProductCodeMap
                from .sales_from_quote import suggested_product_code_id_for_quote_lines

                grouped_products = group_quote_line_items(main_quote)
                category_to_pc_id = dict(
                    CategoryProductCodeMap.objects.values_list(
                        'product_category_id', 'product_code_id'
                    )
                )
                subcat1_to_pc_id = dict(
                    SubCategory1ProductCodeMap.objects.values_list(
                        'product_sub_category1_id', 'product_code_id'
                    )
                )
                # Get tax rate from the quote
                tax_rate = main_quote.get_tax_rate()
                # Calculate tax for each category
                if grouped_products:
                    from decimal import Decimal
                    grouped_products_with_tax = []
                    for category, items, subtotal in grouped_products:
                        subtotal_decimal = Decimal(str(subtotal))
                        category_tax = subtotal_decimal * tax_rate
                        category_total = subtotal_decimal + category_tax
                        category_cost = Decimal('0')
                        for line_item in items:
                            uc = line_item.product.unit_total_cost
                            unit = Decimal(uc) if uc is not None else Decimal('0')
                            category_cost += unit * Decimal(line_item.quantity)
                        category_cost = category_cost.quantize(Decimal('0.01'))
                        suggested_pc_id = suggested_product_code_id_for_quote_lines(
                            items,
                            category_to_pc_id,
                            subcat1_to_pc_id,
                            category_label=category,
                        )
                        mapped_product_code = None
                        if suggested_pc_id:
                            from product.models import ProductCode

                            mapped_product_code = ProductCode.objects.filter(
                                pk=suggested_pc_id
                            ).first()
                        grouped_products_with_tax.append(
                            (
                                category,
                                items,
                                subtotal,
                                category_tax,
                                category_total,
                                category_cost,
                                mapped_product_code,
                            )
                        )
                    grouped_products = grouped_products_with_tax
                
                # Calculate quote totals
                quote_tax = main_quote.calculate_tax()
                quote_total = main_quote.get_total_with_tax()
        except Exception:
            logging.getLogger(__name__).exception(
                "job_sales: failed to attach tax/mapped product codes to grouped quote categories"
            )

        # Calculate sitework total (primary quote, else latest — same as sitework detail)
        try:
            primary_sitework = (
                job.sitework_quotes.filter(is_primary=True)
                .prefetch_related('sql_quotes__cat')
                .first()
            )
            if not primary_sitework:
                primary_sitework = (
                    job.sitework_quotes.order_by('-id')
                    .prefetch_related('sql_quotes__cat')
                    .first()
                )
            if primary_sitework:
                from .utils import group_sitework_by_category
                categories_data = group_sitework_by_category(primary_sitework)
                sitework_subtotal = Decimal('0')
                for category in categories_data:
                    # Extract numeric value from formatted currency string
                    subtotal_str = category['subtotal'].replace('$', '').replace(',', '')
                    try:
                        sitework_subtotal += Decimal(subtotal_str)
                    except (ValueError, TypeError):
                        pass

                # Add contingency and overhead
                contingency_pct = Decimal('0.05')
                overhead_pct = Decimal('0.28')
                contingency = sitework_subtotal * contingency_pct
                overhead = sitework_subtotal * overhead_pct
                # Sitework is not taxed for accounting/sales.
                sitework_total = sitework_subtotal + contingency + overhead
                sitework_tax = Decimal('0.00')
        except Exception:
            logging.getLogger(__name__).exception(
                "job_sales: failed to calculate sitework total"
            )
        
        # Get product codes for dropdown - only specific codes
        from product.models import ProductCode
        allowed_codes = ['CK', 'PSD', 'FL', 'CR', 'LV', 'PFX', 'WP', 'MX', 'AP', 'SL', 'SLW', 'CTS', 'SS', 'PFF', 'DEL', 'DS', 'BA', 'HD', 'DIS', 'CTQ']
        product_codes = ProductCode.objects.filter(code__in=allowed_codes).order_by('code')
        sl_product_code = product_codes.filter(code='SL').first()
    
    # Track which category totals have already been saved as sales
    # Create a list of saved sale amounts (rounded to 2 decimals for comparison)
    # Use values_list to avoid loading full objects
    saved_totals = list(sales.values_list('sale_amount', flat=True))
    saved_totals = [float(round(amount, 2)) for amount in saved_totals]
    
    context = {
        'job': job,
        'sales': sales,  # Keep for backward compatibility if needed
        'grouped_sales': grouped_sales_list,
        'total_sales_amount': total_sales_amount,
        'main_quote': main_quote,
        'grouped_products': grouped_products,
        'quote_tax': quote_tax,
        'quote_total': quote_total,
        'tax_rate': tax_rate,
        'sitework_total': sitework_total,
        'sitework_subtotal': sitework_subtotal,
        'sitework_tax': sitework_tax,
        'sitework_sale_total': sitework_total + sitework_tax,
        'product_codes': product_codes,
        'sl_product_code': sl_product_code,
        'saved_totals': saved_totals,
        'total_sales_cost': total_sales_cost,
        'total_sales_tax': total_sales_tax,
    }

    if main_quote:
        context['quote_has_lines'] = (
            main_quote.line_items.exists() or main_quote.adhoc_line_items.exists()
        )
    else:
        context['quote_has_lines'] = False

    return render(request, 'job/job_sales.html', context)


@login_required
def job_sale_create(request, job_id):
    """Create a new sale for a job"""
    from .forms import SaleForm
    job = get_object_or_404(Job, pk=job_id)
    
    if request.method == 'POST':
        form = SaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.job = job
            # Set created_by to current user if authenticated, otherwise None
            sale.created_by = request.user if request.user.is_authenticated else None
            try:
                sale.save()
                messages.success(request, 'Sale created successfully.')
                return redirect('job:job_sales', job_id=job.id)
            except Exception as e:
                messages.error(request, f'Error creating sale: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SaleForm()
    
    context = {
        'job': job,
        'form': form,
        'is_edit': False,
        'read_only': False,
    }
    
    return render(request, 'job/job_sale_form.html', context)


@login_required
@require_GET
def job_sale_view(request, job_id, sale_id):
    """Read-only sale detail; reuses job_sale_form.html with read_only set."""
    from .forms import SaleForm

    job = get_object_or_404(Job, pk=job_id)
    sale = get_object_or_404(Sale, pk=sale_id, job=job)
    form = SaleForm(instance=sale)
    return render(
        request,
        'job/job_sale_form.html',
        {
            'job': job,
            'form': form,
            'sale': sale,
            'is_edit': False,
            'read_only': True,
        },
    )


@login_required
def job_sale_edit(request, job_id, sale_id):
    """Edit an existing sale"""
    from .forms import SaleForm
    job = get_object_or_404(Job, pk=job_id)
    sale = get_object_or_404(Sale, pk=sale_id, job=job)
    
    if request.method == 'POST':
        form = SaleForm(request.POST, instance=sale)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sale updated successfully.')
            return redirect('job:job_sales', job_id=job.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SaleForm(instance=sale)
    
    context = {
        'job': job,
        'form': form,
        'sale': sale,
        'is_edit': True,
        'read_only': False,
    }
    
    return render(request, 'job/job_sale_form.html', context)


@login_required
@require_POST
def job_sales_bulk_create(request, job_id):
    """Create multiple sales via AJAX"""
    from django.http import JsonResponse
    import json
    from datetime import date, datetime
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    job = get_object_or_404(Job, pk=job_id)
    
    try:
        from decimal import Decimal as D
        from product.models import ProductCode
        from .sales_from_quote import sale_line_comment

        data = json.loads(request.body)
        sales_data = data.get('sales', [])
        
        created_sales = []
        for sale_info in sales_data:
            # Parse sale_date if provided, otherwise use today
            sale_date_str = sale_info.get('sale_date')
            if sale_date_str:
                try:
                    sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d').date()
                except ValueError:
                    sale_date = date.today()
            else:
                sale_date = date.today()
            
            def _opt_decimal(val):
                if val is None or val == '':
                    return None
                try:
                    return D(str(val))
                except Exception:
                    return None

            sale_amt = _opt_decimal(sale_info.get('sale_amount'))
            if sale_amt is None:
                sale_amt = D('0')

            pc_id = sale_info.get('product_code_id')
            product_code = ProductCode.objects.filter(pk=pc_id).first() if pc_id else None
            comment = sale_line_comment(product_code, sale_info.get('category') or '')

            sale = Sale.objects.create(
                job=job,
                product_code_id=pc_id if pc_id else None,
                cost_amount=_opt_decimal(sale_info.get('cost_amount')),
                tax_amount=_opt_decimal(sale_info.get('tax_amount')),
                sale_amount=sale_amt,
                sale_date=sale_date,
                tax=sale_info.get('tax', 'UT'),
                comment=comment,
                created_by=request.user if request.user.is_authenticated else None
            )
            created_sales.append(sale.id)

        if job.sold:
            from .billing_schedule import sync_billing_schedule_sales
            sync_billing_schedule_sales(job, created_by=request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully created {len(created_sales)} sale(s)',
            'created_count': len(created_sales)
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@login_required
def job_sale_delete(request, job_id, sale_id):
    """Delete a sale"""
    job = get_object_or_404(Job, pk=job_id)
    sale = get_object_or_404(Sale, pk=sale_id, job=job)
    
    sale.delete()
    messages.success(request, 'Sale deleted successfully.')
    
    return redirect('job:job_sales', job_id=job.id)


@login_required
def job_sales_invoice_pdf(request, job_id):
    """Generate PDF invoice for sales"""
    from job.pdf_generator import sales_invoice_pdf_generate
    return sales_invoice_pdf_generate(request, job_id)
