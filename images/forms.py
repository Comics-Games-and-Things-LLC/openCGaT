from django import forms

from images.models import Image


class UploadImage(forms.ModelForm):
    class Meta:
        model = Image
        fields = ['image_src', 'alt_text']


class EditAltText(forms.ModelForm):
    class Meta:
        model = Image
        fields = ['alt_text']