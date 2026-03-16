# Standard Library Imports

# Django Imports
import django_filters
from django import forms
from django.db.models import Q

# Application Imports
from .models import User, Company


class UserFilter(django_filters.FilterSet):
    """
    Filter class for User model with search and ordering capabilities.
    """
    
    DEFAULT_ORDERING = '-date_joined'
    
    search = django_filters.CharFilter(
        method='search_query',
        label='Search',
        widget=forms.TextInput(attrs={
            'type': 'search',
            'class': 'form-control',
            'placeholder': 'Search by name or email...'
        })
    )
    
    company = django_filters.ModelChoiceFilter(
        queryset=Company.objects.all(),
        label='Company',
        empty_label='All Companies',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    is_active = django_filters.ChoiceFilter(
        label='Status',
        empty_label='All Status',
        choices=[
            (True, 'Active'),
            (False, 'Inactive'),
        ],
        widget=forms.Select
    )
    
    is_staff = django_filters.ChoiceFilter(
        label='Role',
        empty_label='All Roles',
        choices=[
            (True, 'Staff'),
            (False, 'Regular User'),
        ],
        widget=forms.Select
    )
    
    ordering = django_filters.OrderingFilter(
        empty_label='Sort By',
        label='Sort By',
        choices=[
            ('full_name', 'Name (A-Z)'),
            ('-full_name', 'Name (Z-A)'),
            ('email', 'Email (A-Z)'),
            ('-email', 'Email (Z-A)'),
            ('date_joined', 'Joined (Oldest First)'),
            ('-date_joined', 'Joined (Newest First)'),
            ('updated_at', 'Updated (Oldest First)'),
            ('-updated_at', 'Updated (Newest First)'),
        ],
        initial=DEFAULT_ORDERING,
        widget=forms.Select
    )
    
    def search_query(self, queryset, name, value):
        """
        Custom search method that searches across multiple fields.
        """
        value = value.strip()
        if not value:
            return queryset
        
        query = Q(full_name__icontains=value)
        query |= Q(email__icontains=value)
        query |= Q(company__company_name__icontains=value)
        
        return queryset.filter(query).distinct()
    
    class Meta:
        model = User
        fields = ['search', 'company', 'is_active', 'is_staff', 'ordering']
    
    def __init__(self, data=None, *args, **kwargs):
        """
        Initialize filter with default ordering if not provided.
        """
        if data and data.get('page') and not data.get('ordering'):
            data = data.copy()
            data['ordering'] = self.DEFAULT_ORDERING
        
        super().__init__(data, *args, **kwargs)
        
        # Add Bootstrap classes to form widgets
        self.filters['company'].field.widget.attrs.update({'class': 'form-select'})
        self.filters['is_active'].field.widget.attrs.update({'class': 'form-select'})
        self.filters['is_staff'].field.widget.attrs.update({'class': 'form-select'})
        self.filters['ordering'].field.widget.attrs.update({'class': 'form-select'})

