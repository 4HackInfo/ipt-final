from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, SlipCode

class StudentRegistrationForm(UserCreationForm):
    student_id = forms.CharField(max_length=20, required=True, 
                                 widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024-0001'}))
    course = forms.ChoiceField(choices=User.COURSE_CHOICES, required=True,
                               widget=forms.Select(attrs={'class': 'form-control'}))
    year_level = forms.IntegerField(initial=1, disabled=True, 
                                    widget=forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
                                    help_text="All NSTP students are first year")
    company = forms.ChoiceField(choices=User.COMPANY_CHOICES, required=True,
                                widget=forms.Select(attrs={'class': 'form-control'}))
    contact_number = forms.CharField(max_length=15, required=True,
                                     widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 09123456789'}))
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'student_id', 
                  'course', 'year_level', 'company', 'contact_number', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make year_level readonly and set to 1
        self.fields['year_level'].widget.attrs['readonly'] = True
        self.fields['year_level'].initial = 1

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

class TimeInForm(forms.Form):
    student_id = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Student ID'}))
    slip_code = forms.CharField(max_length=10, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Slip Code'}))

class TimeOutForm(forms.Form):
    student_id = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Student ID'}))
    slip_code = forms.CharField(max_length=10, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Slip Code'}))

class GenerateSlipForm(forms.Form):
    num_codes = forms.IntegerField(min_value=1, max_value=500, initial=1, 
                                   widget=forms.NumberInput(attrs={'class': 'form-control'}))
    code_type = forms.ChoiceField(choices=[('timein', 'Time In'), ('timeout', 'Time Out')],
                                  widget=forms.Select(attrs={'class': 'form-control'}))
    
    # Option to manually enter codes instead of auto-generating
    manual_codes = forms.CharField(
        required=False, 
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Enter codes manually, one per line (e.g.,\nfdc4xd\nfsxcdf\nasdfx)'}),
        help_text="Enter codes manually (one per line) or leave empty for auto-generation"
    )