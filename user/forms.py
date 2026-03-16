from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

# Internal Imports
from .models import User
from . import helpers


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'full_name', 'company')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('email', 'full_name', 'company', 'is_active')


class UserCreateForm(forms.ModelForm):
    """Form for creating a new user."""
    
    class Meta:
        model = User
        fields = ['full_name', 'email', 'is_active', 'is_staff']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
    def save(self, commit=True):
        user = super().save(commit=False)
    
        # Generate random password
        password = helpers.generate_random_password()
        user.set_password(password)
        
        if commit:
            user.save()
            # Send credentials email
            helpers.send_credentials_email(user, password)
        
        return user
    


class UserUpdateForm(forms.ModelForm):
    """Form for updating user information."""
    
    class Meta:
        model = User
        fields = ['full_name', 'email', 'is_active', 'is_staff']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email address'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
