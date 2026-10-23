from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        data = form.cleaned_data
        user.first_name = data.get('first_name', '')
        user.last_name  = data.get('last_name', '')
        user.phone      = data.get('phone', '')

        # Auto-generate a unique username from email if not set
        if not user.username:
            user.username = self._generate_username(user.email)

        if commit:
            user.save()
        return user

    def _generate_username(self, email):
        """Generate a unique username from the email prefix."""
        from accounts.models import User
        base = email.split('@')[0].lower()
        # Strip special characters
        import re
        base = re.sub(r'[^a-z0-9_]', '', base) or 'user'
        username = base
        counter  = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{counter}'
            counter += 1
        return username

    def get_login_redirect_url(self, request):
        """
        Send admin/staff to dashboard,
        customers to home after login.
        """
        if request.user.is_authenticated and request.user.is_admin_or_staff:
            return '/dashboard/'
        return '/'


class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if not user.first_name:
            user.first_name = data.get('first_name', '')
        if not user.last_name:
            user.last_name = data.get('last_name', '')
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # Auto-generate username for social signups
        if not user.username:
            from accounts.adapters import AccountAdapter
            adapter = AccountAdapter()
            user.username = adapter._generate_username(user.email)
            user.save(update_fields=['username'])
        return user