from django.contrib import messages
from functools import wraps
from django.shortcuts import redirect

# Staff access control
def user_staff_required(view_func):
    """
    Decorator to check if user is staff.
    
    Usage:
        @user_staff_required
        def my_view(request):
            ...
    
    Checks:
    - User must be authenticated
    - User must be staff (is_staff=True)
    """
    
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "You must be logged in to access this page.")
            return redirect('account_login')
        
        if not request.user.is_staff:
            messages.error(
                request,
                "You must be a staff member to access this page. "
                "Please contact your administrator if you need access."
            )
            return redirect('dashboard:index')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
    