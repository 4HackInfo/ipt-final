from django.utils import timezone
from datetime import timedelta
from .models import SystemSettings, AttendanceRecord, SlipCode, User
from django.db.models import Count, Q

def is_system_active():
    """Check if system is active (time is before Sunday 12:00 AM)"""
    now = timezone.now()
    # Get the next Sunday at 12:00 AM
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 0:
        # It's Sunday, check if before 12:00 AM? Actually 12:00 AM is start of Sunday
        # System resets Sunday 12:00 AM, so it's active until next Sunday 12:00 AM
        next_sunday = now + timedelta(days=7)
    else:
        next_sunday = now + timedelta(days=days_until_sunday)
    
    next_sunday = next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # System is active if current time is before next Sunday 12:00 AM
    return now < next_sunday

def get_week_start(date=None):
    """Get the start of week (Sunday) for a given date"""
    if date is None:
        date = timezone.now().date()
    return date - timedelta(days=date.weekday() + 1 if date.weekday() != 6 else 0)

def calculate_attendance_summary(week_start=None):
    """Calculate attendance summary for a given week"""
    if week_start is None:
        week_start = get_week_start()
    
    week_end = week_start + timedelta(days=6)
    
    students = User.objects.filter(role='student')
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
            attendance_stats['absent'] += 1
    
    return {
        'total_students': total_students,
        'stats': attendance_stats,
        'week_start': week_start,
        'week_end': week_end,
    }