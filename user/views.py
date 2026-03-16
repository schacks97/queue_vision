from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import DetailView, UpdateView, DeleteView, CreateView
from django.urls import reverse_lazy
from django.db.models import Q
from django_filters.views import FilterView
from django.utils.decorators import method_decorator

# Internal Imports
from .models import User, Company
from .filters import UserFilter
from .forms import UserUpdateForm, UserCreateForm
from .actions import UserManagement
from .decorators import user_staff_required


@method_decorator(user_staff_required, name='dispatch')
class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create a new user.
    """
    model = User
    form_class = UserCreateForm
    template_name = 'user/user_create.html'
    permission_required = 'user.add_user'
    success_url = reverse_lazy('user:user_list')
    
    def form_valid(self, form):
        form.instance.company = self.request.user.company
        messages.success(self.request, f'User {form.instance.full_name} created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New User'
        context['button_text'] = 'Create User'
        return context


@method_decorator(user_staff_required, name='dispatch')
class UserListView(LoginRequiredMixin, FilterView):
    """
    Display a list of all users with filtering and pagination.
    Uses django-filters for advanced filtering capabilities.
    """
    model = User
    template_name = 'user/user_list.html'
    context_object_name = 'users'
    filterset_class = UserFilter
    paginate_by = 10
    
    def get_queryset(self):
        """Get optimized queryset using business logic."""
        queryset = UserManagement.get_user_list_queryset()
        
        # Apply default ordering if not provided
        if not self.request.GET.get('ordering'):
            queryset = queryset.order_by(UserFilter.DEFAULT_ORDERING)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'User Management'
        
        # Add statistics
        stats = UserManagement.get_user_statistics()
        context['total_users'] = stats['total_users']
        context['active_users'] = stats['active_users']
        context['inactive_users'] = stats['inactive_users']
        context['staff_users'] = stats['staff_users']
        
        # Add companies for filters
        context['companies'] = Company.objects.all()
        
        return context


@method_decorator(user_staff_required, name='dispatch')
class UserDetailView(LoginRequiredMixin, DetailView):
    """
    Display detailed information about a specific user.
    """
    model = User
    template_name = 'user/user_detail.html'
    context_object_name = 'user_obj'
    
    def get_queryset(self):
        """Get optimized queryset."""
        return User.objects.select_related('company')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'User: {self.object.full_name}'
        return context


@method_decorator(user_staff_required, name='dispatch')
class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Update user information.
    """
    model = User
    form_class = UserUpdateForm
    template_name = 'user/user_edit.html'
    permission_required = 'user.change_user'

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        response = super().form_valid(form)
        messages.success(self.request, f'User {self.object.full_name} updated successfully.')
        return response
    
    def get_success_url(self):
        return reverse_lazy('user:user_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Edit User'
        context['button_text'] = 'Update User'
        return context


@method_decorator(user_staff_required, name='dispatch')
class UserDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Delete a user permanently.
    """
    model = User
    template_name = 'user/user_confirm_delete.html'
    success_url = reverse_lazy('user:user_list')
    permission_required = 'user.delete_user'
    
    def post(self, request, *args, **kwargs):
        """Override POST to add success message."""
        self.object = self.get_object()
        user_name = self.object.full_name
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(request, f'User "{user_name}" has been deleted successfully.')
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Delete User: {self.object.full_name}'
        return context


class CompanyLicenseView(LoginRequiredMixin, DetailView):
    """
    Display company license information.
    """
    model = Company
    template_name = 'user/company_license.html'
    context_object_name = 'company'
    
    def get_object(self):
        """Get the current user's company."""
        return self.request.user.company
    
    def get_context_data(self, **kwargs):
        from datetime import date
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Company License'
        
        # Get licenses with calculated days remaining
        licenses = []
        today = date.today()
        for license in self.object.licenses.all().order_by('-valid_to'):
            license_data = {
                'license': license,
                'is_active': license.valid_from <= today <= license.valid_to,
                'is_scheduled': license.valid_from > today,
                'is_expired': license.valid_to < today,
                'days_remaining': (license.valid_to - today).days if license.valid_to >= today else 0
            }
            licenses.append(license_data)
        
        context['licenses'] = licenses
        return context

