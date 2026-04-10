from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden

def role_required(allowed_roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            if request.user.role not in allowed_roles:
                return HttpResponseForbidden("You don't have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def admin_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.role == 'admin')(view_func)

def instructor_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.role in ['instructor', 'coordinator', 'admin'])(view_func)

def student_required(view_func):
    return user_passes_test(lambda u: u.is_authenticated and u.role == 'student')(view_func)