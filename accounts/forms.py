from django import forms
from allauth.account.forms import LoginForm, SignupForm
from core.validators import validate_image_upload
from .models import User


class CustomLoginForm(LoginForm):
    """Login field labelled for username/email sign-in, without placeholders."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        login = self.fields['login']
        login.label = 'Username or email'
        login.widget.attrs.pop('placeholder', None)

        password = self.fields['password']
        password.widget.attrs.pop('placeholder', None)
        # allauth adds a "Forgot your password?" help text here; the login
        # template already renders the reset link, so drop the duplicate.
        password.help_text = ''


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=50, label='First Name')
    last_name  = forms.CharField(max_length=50, label='Last Name')
    phone      = forms.CharField(max_length=20, required=False, label='Phone (optional)')

    field_order = ['first_name', 'last_name', 'email', 'phone', 'password1', 'password2']

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        user.phone      = self.cleaned_data.get('phone', '')
        user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'username', 'phone', 'avatar']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'username':   forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Choose a username for login',
            }),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_avatar(self):
        return validate_image_upload(self.cleaned_data.get('avatar'))