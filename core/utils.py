from django.utils import timezone
from datetime import timedelta
from .models import SystemSettings, AttendanceRecord, SlipCode, User
from django.db.models import Count, Q

def is_system_active():
    """
    Check if system is active for student submissions.
    Normal schedule: Saturdays from 6:00 AM to 11:59 PM
    Admin can override anytime with Start Now button
    """
    now = timezone.now()
    
    # Check for admin override first (highest priority)
    try:
        settings = SystemSettings.objects.get(id=1)
        if settings.is_override_active:
            # Check if override hasn't expired (max 48 hours)
            if settings.override_until and now < settings.override_until:
                return True
            else:
                # Override expired, turn it off
                settings.is_override_active = False
                settings.override_until = None
                settings.save()
    except SystemSettings.DoesNotExist:
        pass
    
    # Normal schedule: Saturday only, 6:00 AM to 11:59 PM
    # Saturday is weekday 5 (Monday=0, Sunday=6)
    if now.weekday() == 5:  # Saturday
        # Check if time is between 6:00 AM and 11:59 PM
        if now.hour >= 6:  # 6:00 AM or later
            return True
    
    return False

def get_week_start(date=None):
    """Get the start of week (Saturday) for a given date"""
    if date is None:
        date = timezone.now().date()
    
    # Calculate days to subtract to get to Saturday
    days_to_subtract = (date.weekday() + 2) % 7
    return date - timedelta(days=days_to_subtract)


def calculate_attendance_summary(week_start=None, company_filter=None):
    """Calculate attendance summary for a given week"""
    if week_start is None:
        week_start = get_week_start()
    
    week_end = week_start + timedelta(days=6)
    
    # Get students with optional company filter
    students = User.objects.filter(role='student')
    if company_filter:
        students = students.filter(company=company_filter)
    
    total_students = students.count()
    
    attendance_stats = {
        'present': 0,
        'absent': 0,
        'late': 0,
        'cutting': 0,
    }
    
    for student in students:
        record = AttendanceRecord.objects.filter(
            user=student,
            week_start=week_start
        ).first()
        
        if record:
            attendance_stats[record.status] += 1
        else:
            # No record means absent
            attendance_stats['absent'] += 1
    
    return {
        'total_students': total_students,
        'stats': attendance_stats,
        'week_start': week_start,
        'week_end': week_end,
    }

def get_next_saturday():
    """Get the next Saturday date"""
    today = timezone.now().date()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and timezone.now().hour >= 6:
        days_until_saturday = 7
    return today + timedelta(days=days_until_saturday)

def can_override_system():
    """Admin can always override the system (Start Now button always available)"""
    return True  # Admin can start anytime