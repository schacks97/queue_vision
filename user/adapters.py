from allauth.account.adapter import DefaultAccountAdapter

class NoSignupAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False
    
    def get_user_display(self, user):
        """
        Return the user's display name.
        Since our User model uses 'email' instead of 'username',
        we return the full_name or email.
        """
        return user.full_name if hasattr(user, 'full_name') and user.full_name else user.email