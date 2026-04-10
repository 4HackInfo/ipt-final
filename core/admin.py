from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, SlipCode, AttendanceRecord, SystemSettings

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'student_id')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('role', 'student_id', 'course', 'year_level', 'contact_number')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('role', 'student_id', 'course', 'year_level', 'contact_number')}),
    )

admin.site.register(User, CustomUserAdmin)
admin.site.register(SlipCode)
admin.site.register(AttendanceRecord)
admin.site.register(SystemSettings)