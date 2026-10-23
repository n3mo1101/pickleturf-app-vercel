from django import forms
from .models import Category, InventoryItem, RentalRecord


class CategoryForm(forms.ModelForm):
    class Meta:
        model  = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Paddles, Balls, Shoes',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
            }),
        }


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model  = InventoryItem
        fields = [
            'name', 'category', 'description',
            'item_type', 'sale_price', 'rent_price',
            'stock', 'image', 'is_active',
        ]
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control'}),
            'category':    forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'item_type':   forms.Select(attrs={'class': 'form-select', 'id': 'id_item_type'}),
            'sale_price':  forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'rent_price':  forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'stock':       forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned   = super().clean()
        item_type = cleaned.get('item_type')
        if item_type in (InventoryItem.ItemType.SALE, InventoryItem.ItemType.BOTH):
            if not cleaned.get('sale_price'):
                self.add_error('sale_price', 'Sale price is required.')
        if item_type in (InventoryItem.ItemType.RENT, InventoryItem.ItemType.BOTH):
            if not cleaned.get('rent_price'):
                self.add_error('rent_price', 'Rent price is required.')
        return cleaned


class StockAdjustForm(forms.Form):
    ACTION_CHOICES = [('add', 'Add Stock'), ('deduct', 'Deduct Stock')]
    action   = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reason (optional)',
        }),
    )


class RentalCreateForm(forms.Form):
    """
    Renter info collected once at checkout.
    Item quantities are handled in the template/view directly.
    """
    renter_name = forms.CharField(
        max_length=100,
        label='Renter Name',
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'Full name of renter',
        }),
    )
    renter_contact = forms.CharField(
        max_length=100,
        required=False,
        label='Contact (optional)',
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'Phone number or email',
        }),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows':  2,
            'placeholder': 'Notes (optional)',
        }),
    )