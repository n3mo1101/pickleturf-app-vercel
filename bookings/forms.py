from django import forms
from datetime import date
from courts.models import Court
from .services import get_time_slots, get_availability


class BookingForm(forms.Form):
    """
    Step 1: court + date selection.
    Step 2: available slot checkboxes appear.
    """
    court = forms.ModelChoiceField(
        queryset=Court.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_court',
        }),
        empty_label='— Select a Court —',
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': date.today().isoformat(),
            'id': 'id_date',
        }),
    )
    time_slots = forms.MultipleChoiceField(
        required=False,   # validated manually in view
        widget=forms.CheckboxSelectMultiple(),
        choices=[],       # populated dynamically
        label='Available Time Slots',
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )
    payment_method = forms.ChoiceField(
        choices=[('onsite', 'Pay on-site'), ('online', 'Pay online — GCash/Card')],
        initial='onsite',
        widget=forms.RadioSelect(attrs={'class': 'payment-method-radio'}),
        required=False,
        label='Payment Method',
    )

    def __init__(self, *args, available_slots=None, payments_enabled=True, **kwargs):
        super().__init__(*args, **kwargs)
        if available_slots:
            self.fields['time_slots'].choices = available_slots
        else:
            # Hide slot field until court+date are chosen
            self.fields['time_slots'].widget = forms.HiddenInput()
        # Disable online option when payments are not configured
        if not payments_enabled:
            self.fields['payment_method'].choices = [('onsite', 'Pay on-site (Online payments unavailable)')]
            self.fields['payment_method'].initial = 'onsite'

    def clean_date(self):
        selected = self.cleaned_data['date']
        if selected < date.today():
            raise forms.ValidationError('Please select today or a future date.')
        return selected

    def clean_payment_method(self):
        method = self.cleaned_data.get('payment_method') or 'onsite'
        if method not in ('onsite', 'online'):
            return 'onsite'
        # Force onsite if payments disabled
        from transactions.payments import payments_enabled as _enabled
        if method == 'online' and not _enabled():
            return 'onsite'
        return method


