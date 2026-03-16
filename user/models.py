import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.account.models import EmailAddress


class License(models.Model):
    """Model representing a license."""
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    license_key = models.CharField(max_length=100, unique=True, null=False)
    issued_to = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='licenses')
    valid_from = models.DateField(null=False)
    valid_to = models.DateField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.license_key} - {self.issued_to}"


class Company(models.Model):
    """Model representing a company."""
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    cin = models.CharField(max_length=30, unique=True, null=False)
    company_name = models.CharField(max_length=100, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.cin} - {self.company_name}"


class UserManager(BaseUserManager):
    """Custom user manager for the User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        
        # Check if company is provided
        if 'company' not in extra_fields or extra_fields['company'] is None:
            raise ValueError('Company must be provided to create a user.')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        # If company not provided, prompt for company info or use default
        if 'company' not in extra_fields or extra_fields['company'] is None:
            
            # Create or get a default company for superuser
            company, created = Company.objects.get_or_create(
                cin='99999999999999',
                defaults={ 'company_name': 'Wobot.ai' }
            )
            extra_fields['company'] = company
            
            if created:
                print(f"Created default company: {company.company_name}")
            else:
                print(f"Using existing default company: {company.company_name}")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with email as the unique identifier."""
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    full_name = models.CharField(max_length=100, null=False)
    email = models.EmailField(unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='users')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.email}) - {self.company.company_name}"
    

@receiver(post_save, sender=User)
def post_save_account_email(sender, instance, created, **kwargs):
    try:
        email_address = EmailAddress.objects.get(user_id=instance)
        email_address.email = instance.email
        email_address.verified = False
        email_address.save()
    except:
        pass
