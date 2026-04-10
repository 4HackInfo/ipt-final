from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
import csv
from reportlab.lib.pagesizes import letter, landscape
from .models import User, SlipCode, AttendanceRecord, SystemSettings, GeneratedBatch
from .forms import (
    StudentRegistrationForm, LoginForm, TimeInForm, 
    TimeOutForm, GenerateSlipForm
)
from .decorators import role_required, admin_required, instructor_required, student_required
from .utils import is_system_active, get_week_start, calculate_attendance_summary
from django.http import JsonResponse

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'student'
            user.save()
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    
    return render(request, 'login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')

@login_required
def dashboard_view(request):
    if request.user.role == 'admin':
        return redirect('admin_dashboard')
    elif request.user.role in ['instructor', 'coordinator']:
        return redirect('instructor_dashboard')
    else:
        return redirect('student_dashboard')

@login_required
@admin_required
def admin_dashboard_view(request):
    # Get statistics
    total_students = User.objects.filter(role='student').count()
    total_instructors = User.objects.filter(role='instructor').count()
    
    # Get current week attendance summary
    current_week_start = get_week_start()
    attendance_summary = calculate_attendance_summary(current_week_start)
    
    # Get recent attendance records
    recent_attendance = AttendanceRecord.objects.filter(
        week_start=current_week_start
    ).select_related('user')[:10]
    
    # Get system status
    system_active = is_system_active()
    system_settings, created = SystemSettings.objects.get_or_create(id=1)
    system_settings.is_active = system_active
    system_settings.save()
    
    # Get code statistics
    available_timein = SlipCode.objects.filter(
        code_type='timein', 
        is_used=False,
        expires_at__gt=timezone.now()
    ).count()
    
    available_timeout = SlipCode.objects.filter(
        code_type='timeout', 
        is_used=False,
        expires_at__gt=timezone.now()
    ).count()
    
    # Get company statistics as a LIST (easier for template)
    company_stats_list = []
    companies = User.COMPANY_CHOICES
    
    for company_code, company_name in companies:
        students = User.objects.filter(role='student', company=company_code)
        total = students.count()
        
        present = 0
        absent = 0
        late = 0
        cutting = 0
        
        for student in students:
            record = AttendanceRecord.objects.filter(
                user=student,
                week_start=current_week_start
            ).first()
            
            if record:
                if record.status == 'present':
                    present += 1
                elif record.status == 'late':
                    late += 1
                elif record.status == 'cutting':
                    cutting += 1
            else:
                absent += 1
        
        company_stats_list.append({
            'code': company_code,
            'name': company_name,
            'total': total,
            'present': present,
            'absent': absent,
            'late': late,
            'cutting': cutting,
        })
    
    context = {
        'total_students': total_students,
        'total_instructors': total_instructors,
        'attendance_summary': attendance_summary,
        'recent_attendance': recent_attendance,
        'system_active': system_active,
        'available_timein': available_timein,
        'available_timeout': available_timeout,
        'company_stats_list': company_stats_list,  # Use this instead
    }
    
    return render(request, 'dashboard/admin_dashboard.html', context)

@login_required
@instructor_required
def instructor_dashboard_view(request):
    # Get all students
    students = User.objects.filter(role='student')
    
    # Get current week attendance
    current_week_start = get_week_start()
    attendance_summary = calculate_attendance_summary(current_week_start)
    
    # Get attendance records for this week
    attendance_records = []
    for student in students:
        record = AttendanceRecord.objects.filter(
            user=student,
            week_start=current_week_start
        ).first()
        attendance_records.append({
            'student': student,
            'record': record,
        })
    
    context = {
        'students': students,
        'attendance_records': attendance_records,
        'attendance_summary': attendance_summary,
        'week_start': current_week_start,
    }
    
    return render(request, 'dashboard/instructor_dashboard.html', context)

@login_required
@instructor_required
def attendance_report_view(request):
    # Get filter parameters
    week_start_str = request.GET.get('week_start', '')
    company_filter = request.GET.get('company', '')
    status_filter = request.GET.get('status', '')
    
    if week_start_str:
        from datetime import datetime
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    else:
        week_start = get_week_start()
    
    # Get ALL students (filter by company if selected)
    all_students = User.objects.filter(role='student')
    
    if company_filter:
        all_students = all_students.filter(company=company_filter)
    
    # Get attendance records for the selected week
    attendance_records = {}
    for record in AttendanceRecord.objects.filter(week_start=week_start).select_related('user'):
        attendance_records[record.user.id] = record
    
    # Create a list combining all students with their attendance records
    combined_data = []
    for student in all_students:
        record = attendance_records.get(student.id)
        
        if record:
            # Student has attendance record
            combined_data.append({
                'student': student,
                'record': record,
                'status': record.status,
                'time_in': record.time_in,
                'time_out': record.time_out,
                'date': record.date,
            })
        else:
            # Student has NO attendance record - mark as ABSENT
            combined_data.append({
                'student': student,
                'record': None,
                'status': 'absent',
                'time_in': None,
                'time_out': None,
                'date': week_start,
            })
    
    # Apply status filter if selected
    if status_filter:
        combined_data = [item for item in combined_data if item['status'] == status_filter]
    
    # Pagination
    paginator = Paginator(combined_data, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get summary (this already includes absent students from utils function)
    summary = calculate_attendance_summary(week_start, company_filter)
    
    # Get available weeks (last 8 weeks)
    from datetime import timedelta
    weeks = []
    for i in range(8):
        week_date = get_week_start(timezone.now().date() - timedelta(weeks=i))
        weeks.append({
            'date': week_date,
            'display': week_date.strftime('%B %d, %Y')
        })
    
    context = {
        'page_obj': page_obj,
        'summary': summary,
        'weeks': weeks,
        'selected_week': week_start,
        'company_filter': company_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'reports/attendance_report.html', context)


@login_required
@student_required
def student_dashboard_view(request):
    # Get student's attendance records
    attendance_records = AttendanceRecord.objects.filter(
        user=request.user
    ).order_by('-date')[:10]
    
    # Get current week status
    current_week_start = get_week_start()
    current_record = AttendanceRecord.objects.filter(
        user=request.user,
        week_start=current_week_start
    ).first()
    
    # For code availability - check if there are ANY unused codes available
    # Students don't have assigned codes anymore, they use any available code
    has_available_timein = SlipCode.objects.filter(
        code_type='timein',
        is_used=False,
        expires_at__gt=timezone.now()
    ).exists()
    
    has_available_timeout = SlipCode.objects.filter(
        code_type='timeout',
        is_used=False,
        expires_at__gt=timezone.now()
    ).exists()
    
    context = {
        'attendance_records': attendance_records,
        'current_record': current_record,
        'system_active': is_system_active(),
        'has_available_timein': has_available_timein,
        'has_available_timeout': has_available_timeout,
    }
    
    return render(request, 'dashboard/student_dashboard.html', context)

@login_required
@student_required
def time_in_view(request):
    if not is_system_active():
        messages.error(request, 'The attendance system is currently closed. Please check back next week.')
        return redirect('student_dashboard')
    
    # Check if student already timed in this week
    current_week_start = get_week_start()
    existing_record = AttendanceRecord.objects.filter(
        user=request.user,
        week_start=current_week_start
    ).first()
    
    if existing_record and existing_record.time_in:
        messages.warning(request, 'You have already timed in for this week.')
        return redirect('student_dashboard')
    
    if request.method == 'POST':
        form = TimeInForm(request.POST)
        if form.is_valid():
            student_id = form.cleaned_data['student_id']
            slip_code = form.cleaned_data['slip_code'].strip().lower()
            
            # Verify student ID matches logged in user
            if student_id != request.user.student_id:
                messages.error(request, 'Student ID does not match your account.')
                return redirect('time_in')
            
            # Verify slip code exists in database and is unused
            try:
                # Look for the code in database - removed the 'user' filter since codes aren't assigned to specific students
                code = SlipCode.objects.get(
                    code=slip_code,
                    code_type='timein',
                    is_used=False,
                    expires_at__gt=timezone.now()
                )
                
                # Mark code as used
                code.is_used = True
                code.used_by = request.user
                code.used_at = timezone.now()
                code.save()
                
                # Create or update attendance record
                record, created = AttendanceRecord.objects.get_or_create(
                    user=request.user,
                    week_start=current_week_start,
                    defaults={'time_in': timezone.now(), 'time_in_code': code}
                )
                
                if not created and not record.time_in:
                    record.time_in = timezone.now()
                    record.time_in_code = code
                    record.save()
                
                messages.success(request, f'Time in successful at {timezone.now().strftime("%I:%M %p")}!')
                return redirect('student_dashboard')
                
            except SlipCode.DoesNotExist:
                messages.error(request, 'Invalid, expired, or already used time-in code.')
    else:
        form = TimeInForm()
    
    # Check if there are any available time-in codes
    has_available_codes = SlipCode.objects.filter(
        code_type='timein',
        is_used=False,
        expires_at__gt=timezone.now()
    ).exists()
    
    if not has_available_codes:
        messages.warning(request, 'No time-in codes are currently available. Please contact your instructor.')
    
    return render(request, 'attendance/time_in.html', {'form': form, 'has_available_codes': has_available_codes})

@login_required
@student_required
def time_out_view(request):
    if not is_system_active():
        messages.error(request, 'The attendance system is currently closed. Please check back next week.')
        return redirect('student_dashboard')
    
    # Check if student has timed in
    current_week_start = get_week_start()
    existing_record = AttendanceRecord.objects.filter(
        user=request.user,
        week_start=current_week_start
    ).first()
    
    if not existing_record or not existing_record.time_in:
        messages.warning(request, 'You must time in first before timing out.')
        return redirect('student_dashboard')
    
    if existing_record.time_out:
        messages.warning(request, 'You have already timed out for this week.')
        return redirect('student_dashboard')
    
    if request.method == 'POST':
        form = TimeOutForm(request.POST)
        if form.is_valid():
            student_id = form.cleaned_data['student_id']
            slip_code = form.cleaned_data['slip_code'].strip().lower()
            
            # Verify student ID matches logged in user
            if student_id != request.user.student_id:
                messages.error(request, 'Student ID does not match your account.')
                return redirect('time_out')
            
            # Verify slip code exists in database and is unused
            try:
                # Look for the code in database - removed the 'user' filter since codes aren't assigned to specific students
                code = SlipCode.objects.get(
                    code=slip_code,
                    code_type='timeout',
                    is_used=False,
                    expires_at__gt=timezone.now()
                )
                
                # Mark code as used
                code.is_used = True
                code.used_by = request.user
                code.used_at = timezone.now()
                code.save()
                
                # Update attendance record
                existing_record.time_out = timezone.now()
                existing_record.time_out_code = code
                existing_record.save()
                
                messages.success(request, f'Time out successful at {timezone.now().strftime("%I:%M %p")}!')
                return redirect('student_dashboard')
                
            except SlipCode.DoesNotExist:
                messages.error(request, 'Invalid, expired, or already used time-out code.')
    else:
        form = TimeOutForm()
    
    # Check if there are any available time-out codes
    has_available_codes = SlipCode.objects.filter(
        code_type='timeout',
        is_used=False,
        expires_at__gt=timezone.now()
    ).exists()
    
    if not has_available_codes:
        messages.warning(request, 'No time-out codes are currently available. Please contact your instructor.')
    
    return render(request, 'attendance/time_out.html', {'form': form, 'has_available_codes': has_available_codes})

@login_required
@admin_required
def generate_slip_codes_view(request):
    """Generate slip codes - stores them in database immediately upon generation"""
    
    if request.method == 'POST':
        form = GenerateSlipForm(request.POST)
        if form.is_valid():
            num_codes = form.cleaned_data['num_codes']
            code_type = form.cleaned_data['code_type']
            manual_codes = form.cleaned_data.get('manual_codes', '').strip()
            
            current_week_start = get_week_start()
            generated_codes_list = []
            batch = None
            
            # Create batch record
            batch = GeneratedBatch.objects.create(
                code_type=code_type,
                num_codes=num_codes if not manual_codes else len(manual_codes.splitlines()),
                generated_by=request.user,
                week_start=current_week_start
            )
            
            if manual_codes:
                # Use manually entered codes
                codes = [code.strip().lower() for code in manual_codes.splitlines() if code.strip()]
                
                for code in codes:
                    # Check if code already exists
                    if SlipCode.objects.filter(code=code).exists():
                        messages.warning(request, f'Code "{code}" already exists and was skipped.')
                        continue
                    
                    slip_code = SlipCode.objects.create(
                        code=code,
                        code_type=code_type,
                        week_start=current_week_start,
                        batch_number=batch.batch_number
                    )
                    generated_codes_list.append({
                        'code': slip_code.code,
                        'type': code_type
                    })
            else:
                # Auto-generate codes
                for i in range(num_codes):
                    slip_code = SlipCode.objects.create(
                        code_type=code_type,
                        week_start=current_week_start,
                        batch_number=batch.batch_number
                    )
                    generated_codes_list.append({
                        'code': slip_code.code,
                        'type': code_type
                    })
            
            if generated_codes_list:
                # Store generated codes in session for printing
                request.session['generated_codes'] = generated_codes_list
                request.session['current_batch'] = batch.batch_number
                
                messages.success(
                    request, 
                    f'Successfully generated {len(generated_codes_list)} {code_type} codes. '
                    f'Batch: {batch.batch_number}'
                )
                return redirect('print_slips')
            else:
                messages.error(request, 'No valid codes were generated.')
                return redirect('generate_slips')
    else:
        form = GenerateSlipForm()
    
    # Get recent batches for display
    recent_batches = GeneratedBatch.objects.all().order_by('-generated_at')[:10]
    
    # Get unused codes count
    unused_timein = SlipCode.objects.filter(
        code_type='timein', 
        is_used=False,
        expires_at__gt=timezone.now()
    ).count()
    
    unused_timeout = SlipCode.objects.filter(
        code_type='timeout', 
        is_used=False,
        expires_at__gt=timezone.now()
    ).count()
    
    context = {
        'form': form,
        'recent_batches': recent_batches,
        'unused_timein': unused_timein,
        'unused_timeout': unused_timeout,
    }
    
    return render(request, 'slip_codes/generate_slips.html', context)

@login_required
@admin_required
def print_slips_view(request):
    generated_codes = request.session.get('generated_codes', [])
    
    if not generated_codes:
        messages.warning(request, 'No codes to print. Please generate codes first.')
        return redirect('generate_slips')
    
    context = {
        'codes': generated_codes,
    }
    
    return render(request, 'slip_codes/print_slips.html', context)

@login_required
@admin_required
def download_slips_pdf(request):
    generated_codes = request.session.get('generated_codes', [])
    
    if not generated_codes:
        messages.warning(request, 'No codes to download.')
        return redirect('generate_slips')
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), 
                           rightMargin=36, leftMargin=36, 
                           topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []
    
    # Extract just the code strings from the generated_codes list
    timein_codes = [c['code'] for c in generated_codes if c.get('type') == 'timein']
    timeout_codes = [c['code'] for c in generated_codes if c.get('type') == 'timeout']
    
    # Create a 10x10 grid (10 rows x 10 columns = 100 codes)
    def create_code_grid(codes, title, title_color, code_color):
        story_parts = []
        
        # Title with color
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=title_color,
            alignment=1,
            spaceAfter=20
        )
        story_parts.append(Paragraph(title, title_style))
        
        # Subtitle
        subtitle = Paragraph(f"Total: {len(codes)} codes | One-time use only | Valid until end of week", styles['Normal'])
        story_parts.append(subtitle)
        story_parts.append(Spacer(1, 10))
        
        # Create table data: 10 columns x (number of rows needed)
        num_rows = (len(codes) + 9) // 10  # Ceiling division
        
        # Prepare table data
        table_data = []
        
        # Create the grid
        for row in range(num_rows):
            data_row = []
            for col in range(10):
                idx = row * 10 + col
                if idx < len(codes):
                    # Create a cell with colored code text
                    code_num = idx + 1
                    
                    # Get color as hex string for the background
                    bg_color = '#e8f5e9' if title_color == colors.green else '#ffebee'
                    
                    code_text = f"""
                    <table border="1" cellpadding="5" cellspacing="0" width="100%">
                        <tr>
                            <td align="center" bgcolor="#f0f0f0" width="30%">
                                <font size="8">#{code_num}</font>
                            </td>
                            <td align="center" bgcolor="{bg_color}">
                                <font size="11" face="Courier" color="{code_color}"><b>{codes[idx]}</b></font>
                            </td>
                        </tr>
                        <tr>
                            <td align="center" colspan="2" height="30">
                                <font size="7">__________________</font>
                            </td>
                        </tr>
                    </table>
                    """
                    data_row.append(Paragraph(code_text, styles['Normal']))
                else:
                    # Empty cell
                    data_row.append(Paragraph("", styles['Normal']))
            table_data.append(data_row)
        
        # Create table with 10 columns
        col_widths = [0.9*inch] * 10
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        
        story_parts.append(table)
        story_parts.append(Spacer(1, 20))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            alignment=1,
            textColor=colors.grey
        )
        footer = Paragraph("NSTP Attendance System - Slip Code (One-time use only)", footer_style)
        story_parts.append(footer)
        
        return story_parts
    
    # Generate Time In codes grid (Green text)
    if timein_codes:
        story.extend(create_code_grid(timein_codes, "TIME IN SLIP CODES", colors.green, colors.green))
    
    # Add page break if both types exist
    if timein_codes and timeout_codes:
        story.append(PageBreak())
    
    # Generate Time Out codes grid (Red text)
    if timeout_codes:
        story.extend(create_code_grid(timeout_codes, "TIME OUT SLIP CODES", colors.red, colors.red))
    
    doc.build(story)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="nstp_slip_codes.pdf"'
    return response

@login_required
@admin_required
def toggle_system_view(request):
    if request.method == 'POST':
        # This is controlled by the is_system_active() function
        # which checks the actual time
        messages.info(request, 'System status is automatically controlled by time. It resets every Sunday at 12:00 AM.')
    
    return redirect('admin_dashboard')


@login_required
@admin_required
def view_all_codes_view(request):
    """View all generated codes with their status"""
    code_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    
    codes = SlipCode.objects.all().order_by('-created_at')
    
    if code_type:
        codes = codes.filter(code_type=code_type)
    if status == 'used':
        codes = codes.filter(is_used=True)
    elif status == 'unused':
        codes = codes.filter(is_used=False)
    
    # Pagination
    paginator = Paginator(codes, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_codes = SlipCode.objects.count()
    used_codes = SlipCode.objects.filter(is_used=True).count()
    unused_codes = SlipCode.objects.filter(is_used=False).count()
    timein_codes = SlipCode.objects.filter(code_type='timein').count()
    timeout_codes = SlipCode.objects.filter(code_type='timeout').count()
    
    context = {
        'page_obj': page_obj,
        'total_codes': total_codes,
        'used_codes': used_codes,
        'unused_codes': unused_codes,
        'timein_codes': timein_codes,
        'timeout_codes': timeout_codes,
        'current_type': code_type,
        'current_status': status,
    }
    
    return render(request, 'slip_codes/all_codes.html', context)

@login_required
@admin_required
def delete_expired_codes_view(request):
    """Delete expired codes"""
    if request.method == 'POST':
        expired_codes = SlipCode.objects.filter(
            expires_at__lt=timezone.now(),
            is_used=False
        )
        count = expired_codes.count()
        expired_codes.delete()
        messages.success(request, f'Successfully deleted {count} expired codes.')
    return redirect('view_all_codes')

@login_required
@admin_required
def generate_again_view(request):
    """Generate new codes with the same settings as the last batch"""
    
    # Get the last generated batch from session
    last_batch_number = request.session.get('current_batch', '')
    last_generated_codes = request.session.get('generated_codes', [])
    
    if not last_batch_number or not last_generated_codes:
        messages.error(request, 'No previous generation found. Please generate new codes first.')
        return redirect('generate_slips')
    
    # Get the batch type from the last generated codes
    if last_generated_codes:
        code_type = last_generated_codes[0]['type']
        num_codes = len(last_generated_codes)
        
        current_week_start = get_week_start()
        generated_codes_list = []
        
        # Create batch record
        batch = GeneratedBatch.objects.create(
            code_type=code_type,
            num_codes=num_codes,
            generated_by=request.user,
            week_start=current_week_start
        )
        
        # Generate new codes
        for i in range(num_codes):
            slip_code = SlipCode.objects.create(
                code_type=code_type,
                week_start=current_week_start,
                batch_number=batch.batch_number
            )
            generated_codes_list.append({
                'code': slip_code.code,
                'type': code_type
            })
        
        if generated_codes_list:
            # Store generated codes in session for printing
            request.session['generated_codes'] = generated_codes_list
            request.session['current_batch'] = batch.batch_number
            
            messages.success(
                request, 
                f'Successfully generated {len(generated_codes_list)} new {code_type} codes. '
                f'Batch: {batch.batch_number}'
            )
            return redirect('print_slips')
        else:
            messages.error(request, 'Failed to generate new codes.')
            return redirect('print_slips')
    
    return redirect('print_slips')

@login_required
@admin_required
def generate_again_ajax(request):
    """AJAX endpoint to generate new codes with the same settings"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    # Get the last generated batch from session
    last_batch_number = request.session.get('current_batch', '')
    last_generated_codes = request.session.get('generated_codes', [])
    
    if not last_batch_number or not last_generated_codes:
        return JsonResponse({'success': False, 'message': 'No previous generation found'})
    
    # Get the batch type from the last generated codes
    if last_generated_codes:
        code_type = last_generated_codes[0]['type']
        num_codes = len(last_generated_codes)
        
        current_week_start = get_week_start()
        generated_codes_list = []
        
        # Create batch record
        batch = GeneratedBatch.objects.create(
            code_type=code_type,
            num_codes=num_codes,
            generated_by=request.user,
            week_start=current_week_start
        )
        
        # Generate new codes
        for i in range(num_codes):
            slip_code = SlipCode.objects.create(
                code_type=code_type,
                week_start=current_week_start,
                batch_number=batch.batch_number
            )
            generated_codes_list.append({
                'code': slip_code.code,
                'type': code_type
            })
        
        if generated_codes_list:
            # Store generated codes in session for printing
            request.session['generated_codes'] = generated_codes_list
            request.session['current_batch'] = batch.batch_number
            
            return JsonResponse({
                'success': True, 
                'message': f'Generated {len(generated_codes_list)} new codes',
                'batch': batch.batch_number
            })
    
    return JsonResponse({'success': False, 'message': 'Failed to generate codes'})

@login_required
@admin_required
def code_management_view(request):
    """Complete code management dashboard"""
    
    # Get filter parameters
    code_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    
    codes = SlipCode.objects.all().order_by('-created_at')
    
    if code_type:
        codes = codes.filter(code_type=code_type)
    if status == 'used':
        codes = codes.filter(is_used=True)
    elif status == 'unused':
        codes = codes.filter(is_used=False)
    
    # Pagination
    paginator = Paginator(codes, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_codes = SlipCode.objects.count()
    used_codes = SlipCode.objects.filter(is_used=True).count()
    unused_codes = SlipCode.objects.filter(is_used=False).count()
    expired_codes = SlipCode.objects.filter(expires_at__lt=timezone.now(), is_used=False).count()
    
    # Time-in specific stats
    timein_total = SlipCode.objects.filter(code_type='timein').count()
    timein_available = SlipCode.objects.filter(code_type='timein', is_used=False, expires_at__gt=timezone.now()).count()
    timein_used = SlipCode.objects.filter(code_type='timein', is_used=True).count()
    
    # Time-out specific stats
    timeout_total = SlipCode.objects.filter(code_type='timeout').count()
    timeout_available = SlipCode.objects.filter(code_type='timeout', is_used=False, expires_at__gt=timezone.now()).count()
    timeout_used = SlipCode.objects.filter(code_type='timeout', is_used=True).count()
    
    context = {
        'page_obj': page_obj,
        'total_codes': total_codes,
        'used_codes': used_codes,
        'unused_codes': unused_codes,
        'expired_codes': expired_codes,
        'timein_total': timein_total,
        'timein_available': timein_available,
        'timein_used': timein_used,
        'timeout_total': timeout_total,
        'timeout_available': timeout_available,
        'timeout_used': timeout_used,
        'current_type': code_type,
        'current_status': status,
    }
    
    return render(request, 'slip_codes/code_management.html', context)

@login_required
@admin_required
def delete_expired_codes_view(request):
    """Delete expired codes"""
    if request.method == 'POST':
        expired_codes = SlipCode.objects.filter(
            expires_at__lt=timezone.now(),
            is_used=False
        )
        count = expired_codes.count()
        expired_codes.delete()
        messages.success(request, f'Successfully deleted {count} expired codes.')
    return redirect('code_management')

@login_required
@admin_required
def delete_all_unused_codes(request):
    """Delete all unused codes"""
    if request.method == 'POST':
        unused_codes = SlipCode.objects.filter(is_used=False)
        count = unused_codes.count()
        unused_codes.delete()
        messages.success(request, f'Successfully deleted {count} unused codes.')
    return redirect('code_management')

@login_required
@admin_required
def delete_single_code(request):
    """Delete a single code via AJAX"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        code = data.get('code')
        
        try:
            slip_code = SlipCode.objects.get(code=code, is_used=False)
            slip_code.delete()
            return JsonResponse({'success': True})
        except SlipCode.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Code not found or already used'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@admin_required
def code_report_pdf(request):
    """Generate PDF report of all codes"""
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    
    codes = SlipCode.objects.all().order_by('-created_at')
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=20, alignment=1, spaceAfter=30)
    title = Paragraph("Slip Codes Report", title_style)
    story.append(title)
    
    # Subtitle
    subtitle = Paragraph(f"Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal'])
    story.append(subtitle)
    story.append(Spacer(1, 20))
    
    # Statistics
    total_codes = codes.count()
    used_codes = codes.filter(is_used=True).count()
    unused_codes = codes.filter(is_used=False).count()
    
    stats_data = [
        ['Total Codes', str(total_codes)],
        ['Used Codes', str(used_codes)],
        ['Unused Codes', str(unused_codes)],
        ['Time-In Codes', str(codes.filter(code_type='timein').count())],
        ['Time-Out Codes', str(codes.filter(code_type='timeout').count())],
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch, 1*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Codes table
    table_data = [['Code', 'Type', 'Status', 'Used By', 'Student ID', 'Batch', 'Created', 'Expires']]
    
    for code in codes[:100]:  # Limit to 100 for PDF
        table_data.append([
            code.code,
            code.code_type.upper(),
            'Used' if code.is_used else 'Available',
            code.used_by.get_full_name() if code.used_by else '-',
            code.used_by.student_id if code.used_by else '-',
            code.batch_number or '-',
            code.created_at.strftime('%Y-%m-%d %H:%M'),
            code.expires_at.strftime('%Y-%m-%d %H:%M'),
        ])
    
    table = Table(table_data, colWidths=[1*inch, 0.8*inch, 0.8*inch, 1.2*inch, 0.8*inch, 1*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="slip_codes_report.pdf"'
    return response

@login_required
@instructor_required
def export_attendance_csv(request):
    # Get filter parameters
    week_start_str = request.GET.get('week_start', '')
    company_filter = request.GET.get('company', '')
    status_filter = request.GET.get('status', '')
    
    if week_start_str:
        from datetime import datetime
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    else:
        week_start = get_week_start()
    
    # Get ALL students with optional company filter
    all_students = User.objects.filter(role='student')
    if company_filter:
        all_students = all_students.filter(company=company_filter)
    
    # Get attendance records for the selected week
    attendance_records = {}
    for record in AttendanceRecord.objects.filter(week_start=week_start).select_related('user'):
        attendance_records[record.user.id] = record
    
    # Create combined data with status
    combined_data = []
    for student in all_students:
        record = attendance_records.get(student.id)
        
        if record:
            status = record.status
            # Check if time_in and time_out exist (regardless of time)
            time_in_status = 'PASSED' if record.time_in else 'NOT PASSED'
            time_out_status = 'PASSED' if record.time_out else 'NOT PASSED'
            date = record.date
        else:
            status = 'absent'
            time_in_status = 'NOT PASSED'
            time_out_status = 'NOT PASSED'
            date = week_start
        
        combined_data.append({
            'student': student,
            'status': status,
            'time_in_status': time_in_status,
            'time_out_status': time_out_status,
            'date': date,
        })
    
    # Apply status filter if selected
    if status_filter:
        combined_data = [item for item in combined_data if item['status'] == status_filter]
    
    # Create filename
    filename_parts = ['attendance_report', week_start.strftime('%Y-%m-%d')]
    if company_filter:
        filename_parts.append(company_filter.lower())
    if status_filter:
        filename_parts.append(status_filter)
    
    filename = '_'.join(filename_parts)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    
    writer = csv.writer(response)
    
    # Header row
    writer.writerow(['Student ID', 'Name', 'Course', 'Company', 'Year Level', 'Date', 'Time In Status', 'Time Out Status', 'Overall Status'])
    
    # Data rows
    for item in combined_data:
        # Format year level
        year_level = f"{item['student'].year_level} Year"
        
        # Format date
        date_str = item['date'].strftime('%d/%m/%Y')
        
        writer.writerow([
            item['student'].student_id,
            item['student'].get_full_name(),
            item['student'].get_course_display(),
            item['student'].get_company_display(),
            year_level,
            date_str,
            item['time_in_status'],
            item['time_out_status'],
            item['status'].upper()
        ])
    
    return response