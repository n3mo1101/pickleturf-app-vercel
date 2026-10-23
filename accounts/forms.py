from django import forms
from allauth.account.forms import SignupForm
from .models import User


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