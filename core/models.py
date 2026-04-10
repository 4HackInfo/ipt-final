from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
import secrets
import string

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('instructor', 'Instructor'),
        ('coordinator', 'Coordinator'),
        ('admin', 'Admin'),
    )
    
    COURSE_CHOICES = (
        ('BSIT', 'BS Information Technology'),
        ('BSED', 'BS Education'),
        ('BSHM', 'BS Hospitality Management'),
        ('BSCRIM', 'BS Criminology'),
        ('BSTM', 'BS Tourism Management'),
    )
    
    COMPANY_CHOICES = (
        ('ALPHA', 'Alpha Company'),
        ('BRAVO', 'Bravo Company'),
        ('CHARLIE', 'Charlie Company'),
        ('DELTA', 'Delta Company'),
        ('ECHO', 'Echo Company'),
        ('FOXTROT', 'Foxtrot Company'),
        ('GOLF', 'Golf Company'),
        ('HOTEL', 'Hotel Company'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    student_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    course = models.CharField(max_length=20, choices=COURSE_CHOICES, blank=True)
    year_level = models.IntegerField(default=1)  # Default to 1st year
    company = models.CharField(max_length=20, choices=COMPANY_CHOICES, blank=True)
    contact_number = models.CharField(max_length=15, blank=True)
    
    def __str__(self):
        return f"{self.username} - {self.role}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_course_display(self):
        return dict(self.COURSE_CHOICES).get(self.course, self.course)
    
    def get_company_display(self):
        return dict(self.COMPANY_CHOICES).get(self.company, self.company)

class SlipCode(models.Model):
    TYPE_CHOICES = (
        ('timein', 'Time In'),
        ('timeout', 'Time Out'),
    )
    
    code = models.CharField(max_length=10, unique=True, db_index=True)
    code_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    is_used = models.BooleanField(default=False)
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='used_codes')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    week_start = models.DateField()
    batch_number = models.CharField(max_length=20, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_unique_code()
        if not self.expires_at:
            # Code expires after 7 days
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
    
    def generate_unique_code(self):
        while True:
            # Generate 6-8 character alphanumeric code
            code = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
            if not SlipCode.objects.filter(code=code).exists():
                return code
    
    def __str__(self):
        return f"{self.code} - {self.code_type} - {'Used' if self.is_used else 'Available'}"

class AttendanceRecord(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('cutting', 'Cutting Class'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(auto_now_add=True)
    time_in = models.DateTimeField(null=True, blank=True)
    time_out = models.DateTimeField(null=True, blank=True)
    time_in_code = models.ForeignKey(SlipCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_in_records')
    time_out_code = models.ForeignKey(SlipCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='time_out_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='absent')
    week_start = models.DateField()
    
    # New fields for pass/fail status
    time_in_passed = models.BooleanField(default=False)
    time_out_passed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['user', 'date']
    
    def save(self, *args, **kwargs):
        # Set pass/fail based on whether time_in and time_out exist
        self.time_in_passed = self.time_in is not None
        self.time_out_passed = self.time_out is not None
        
        # Determine status based on time_in and time_out
        if self.time_in and self.time_out:
            self.status = 'present'
        elif self.time_in and not self.time_out:
            self.status = 'cutting'
        elif not self.time_in and self.time_out:
            self.status = 'late'
        else:
            self.status = 'absent'
        
        if not self.week_start:
            # Get start of week (Sunday)
            today = self.date or timezone.now().date()
            self.week_start = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.status}"

class SystemSettings(models.Model):
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "System Settings"
    
    def __str__(self):
        return f"System Active: {self.is_active}"

class GeneratedBatch(models.Model):
    """Track batches of generated codes"""
    batch_number = models.CharField(max_length=20, unique=True)
    code_type = models.CharField(max_length=10, choices=SlipCode.TYPE_CHOICES)
    num_codes = models.IntegerField()
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    week_start = models.DateField()
    
    def save(self, *args, **kwargs):
        if not self.batch_number:
            # Generate batch number: BATCH-20241201-001 format
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            last_batch = GeneratedBatch.objects.filter(
                batch_number__startswith=f'BATCH-{date_str}'
            ).order_by('-batch_number').first()
            
            if last_batch:
                last_num = int(last_batch.batch_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.batch_number = f'BATCH-{date_str}-{str(new_num).zfill(3)}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.batch_number} - {self.num_codes} {self.code_type} codes"