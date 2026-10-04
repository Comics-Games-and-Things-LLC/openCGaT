from django import forms
from .models import BoxInventory

class BoxInventoryForm(forms.ModelForm):
    class Meta:
        model = BoxInventory
        fields = ['current_inventory']
