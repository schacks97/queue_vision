import secrets, string
import threading
from django.core.mail import send_mail
from django.conf import settings

def get_message_template(user, password):
    """Generate the email message template."""
    return f"""
Hello {user.full_name},

Your account has been created successfully!

Here are your login credentials:

Name: {user.full_name}
Email: {user.email}
Password: {password}
Company: {user.company.company_name}
CIN: {user.company.cin}

Please login and change your password immediately.

Login URL: {settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'http://localhost:8000'}/accounts/login/

Best regards,
{user.company.company_name} Team
"""


def generate_random_password(length=12):
    """Generate a random password."""
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(characters) for i in range(length))
    return password


def send_credentials_email(user, password):
        """Send email with login credentials to the new user."""
        subject = f'Your Account Credentials - {user.company.company_name}'
        message = get_message_template(user, password)
        
        # Start the email sending in a separate thread
        thread = threading.Thread(target=lambda: send_mail(
            subject, message, settings.EMAIL_HOST_USER, [user.email], fail_silently=False)
            )
        thread.daemon = True
        thread.start()


def generate_license_key(segments=4, segment_length=5):
    alphabet = string.ascii_uppercase + string.digits
    key = '-'.join(''.join(secrets.choice(alphabet) for _ in range(segment_length)) for _ in range(segments))
    # Example: K19F-X7RT-99LP-ZQX2
    return key
