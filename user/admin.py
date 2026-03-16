from django.utils import timezone
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Company, License
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .helpers import generate_license_key


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    
    # Fields to display in the list view
    list_display = ('email', 'full_name', 'company', 'is_staff', 'is_active')
    list_filter = ('company', 'is_staff', 'is_active')
    
    # Fields to display when editing a user
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('full_name', 'company')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('date_joined', 'updated_at')}),
    )

    # Fields to display when creating a user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'company', 'password1', 'password2'),
        }),
    )

    search_fields = ('email', 'full_name')
    ordering = ('email',)
    readonly_fields = ('date_joined', 'updated_at')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'cin', 'created_at')
    search_fields = ('company_name', 'cin')


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('license_key', 'issued_to', 'valid_from', 'valid_to', 'is_active_status')
    list_filter = ('issued_to', 'valid_from', 'valid_to')
    search_fields = ('license_key', 'issued_to__company_name')
    readonly_fields = ('license_key', 'created_at', 'updated_at')
    
    fieldsets = (
        ('License Information', {
            'fields': ('license_key', 'issued_to')
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_status(self, obj):
        """Display whether the license is currently active"""
        today = timezone.now().date()
        
        if obj.valid_from <= today <= obj.valid_to:
            return '✅ Active'
        elif obj.valid_from > today:
            return '🕐 Scheduled'
        else:
            return '❌ Expired'
    is_active_status.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        """Auto-generate license key if not provided and validate dates"""
        
        # Validate that valid_to is not before valid_from
        if obj.valid_to < obj.valid_from:
            from django.contrib import messages
            messages.error(request, 'Valid To date cannot be earlier than Valid From date.')
            return
        
        if not obj.license_key:
            # Generate a unique license key
            obj.license_key = generate_license_key()
            # Ensure uniqueness
            while License.objects.filter(license_key=obj.license_key).exists():
                obj.license_key = generate_license_key()
        super().save_model(request, obj, form, change)
    
