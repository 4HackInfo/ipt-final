from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('instructor-dashboard/', views.instructor_dashboard_view, name='instructor_dashboard'),
    path('student-dashboard/', views.student_dashboard_view, name='student_dashboard'),
    
    # Attendance
    path('time-in/', views.time_in_view, name='time_in'),
    path('time-out/', views.time_out_view, name='time_out'),
    
    # Slip Codes
    path('generate-slips/', views.generate_slip_codes_view, name='generate_slips'),
    path('print-slips/', views.print_slips_view, name='print_slips'),
    path('generate-again/', views.generate_again_view, name='generate_again'),
    path('download-slips-pdf/', views.download_slips_pdf, name='download_slips_pdf'),
    path('all-codes/', views.view_all_codes_view, name='view_all_codes'),
    path('code-management/', views.code_management_view, name='code_management'),  # Add this line
    path('delete-expired-codes/', views.delete_expired_codes_view, name='delete_expired_codes'),
    path('delete-all-unused-codes/', views.delete_all_unused_codes, name='delete_all_unused_codes'),
    path('delete-single-code/', views.delete_single_code, name='delete_single_code'),
    path('code-report-pdf/', views.code_report_pdf, name='code_report_pdf'),
    
    # Reports
    path('attendance-report/', views.attendance_report_view, name='attendance_report'),
    path('export-attendance-csv/', views.export_attendance_csv, name='export_attendance_csv'),
    
    # System
    path('toggle-system/', views.toggle_system_view, name='toggle_system'),
]