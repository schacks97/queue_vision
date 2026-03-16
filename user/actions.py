"""
Business logic for user management.
This module contains all the core business logic for user operations.
"""
from django.db.models import Q, Count
from django.utils import timezone
from .models import User, Company


class UserManagement:
    """
    Handles all business logic related to user operations.
    """
    
    @staticmethod
    def get_user_list_queryset():
        """
        Get optimized queryset for user list.
        Includes select_related for company to reduce queries.
        """
        return User.objects.select_related('company').order_by('-date_joined')
    
    @staticmethod
    def get_user_statistics():
        """
        Get statistics about users.
        Returns: Dict with various user statistics
        """
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = User.objects.filter(is_active=False).count()
        staff_users = User.objects.filter(is_staff=True).count()
        
        # Users per company
        users_by_company = Company.objects.annotate(
            user_count=Count('users')
        ).values('company_name', 'user_count')
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'staff_users': staff_users,
            'users_by_company': list(users_by_company),
        }


class LicenseManagement:
    """
    Handles all business logic related to license operations.
    """
    
    @staticmethod
    def validate_license_key(user) -> bool:
        """
        Validate the license key associated with the user's company.
        Returns True if valid, False otherwise.
        """
        company = user.company
        license = company.license
        
        if not license:
            return False
        
        today = timezone.now().date()
        
        if license.valid_from <= today <= license.valid_to:
            return True
        return False
    
    
        

