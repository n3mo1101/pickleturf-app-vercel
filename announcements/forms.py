from django import forms
from .models import Announcement


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model  = Announcement
        fields = ['title', 'body', 'level', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={
                'class':       'form-control',
                'placeholder': 'Announcement title',
            }),
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows':  3,
                'placeholder': 'Additional details (optional)',
            }),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }