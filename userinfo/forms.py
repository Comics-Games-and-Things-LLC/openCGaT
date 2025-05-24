from django import forms
from django.contrib.auth.models import User
from django_select2 import forms as s2forms


class UserWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = [
        "username__icontains",
        "email__icontains",
    ]


class UserSelectForm(forms.Form):
    users = forms.ModelMultipleChoiceField(queryset=User.objects.filter(is_active=True), widget=UserWidget)
