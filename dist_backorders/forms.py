from django import forms

class FiltersForm(forms.Form):
    search = forms.CharField(required=False)
