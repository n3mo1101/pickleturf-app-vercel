from django import forms
from django.contrib.auth import get_user_model
from .models import OpenPlaySession, OpenPlayParticipant

User = get_user_model()


class OpenPlaySessionForm(forms.ModelForm):
    """Admin creates/edits an open-play session."""

    class Meta:
        model  = OpenPlaySession
        fields = [
            'title', 'description', 'date',
            'start_time', 'end_time', 'capacity', 'fee',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Saturday Morning Open Play',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
            }),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control', 'type': 'time',
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-control', 'type': 'time',
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1,
            }),
            'fee': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'step': '0.01',
            }),
        }

    def clean(self):
        cleaned = super().clean()
        start   = cleaned.get('start_time')
        end     = cleaned.get('end_time')
        if start and end and end <= start:
            raise forms.ValidationError('End time must be after start time.')
        return cleaned


class AddParticipantForm(forms.Form):
    """Admin manually adds a walk-in participant to session."""
    participant_name = forms.CharField(
        max_length=100,
        label='Participant Name',
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'Full name of participant',
        })
    )