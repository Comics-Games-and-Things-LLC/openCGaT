from django import forms
from django.contrib.admin.widgets import AdminDateWidget
from django_select2 import forms as s2forms

from dist_requests.models import DistRequestLine, DistRequest
from intake.models import Distributor


class RequestNameWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "request_name__icontains",
    ]


class DistRequestLineForm(forms.ModelForm):
    distributor = forms.ModelChoiceField(Distributor.objects.all().order_by('dist_name'), required=False,
                                         help_text="Set if not selecting an existing request",
                                         widget=s2forms.ModelSelect2Widget(
                                             search_fields=['dist_name__icontains'],
                                         ))
    request_name = forms.CharField(max_length=300, required=False,
                                   help_text="Set if not selecting an existing request")
    date = forms.DateField(required=False,
                           help_text="Set if not selecting an existing request",
                           widget=AdminDateWidget)

    class Meta:
        model = DistRequestLine
        fields = ['request', 'quantity', 'notes']
        widgets = {
            'request': RequestNameWidget(
                attrs={'required': False,
                       'help_text': 'Select a request or enter a new one below'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super(DistRequestLineForm, self).__init__(*args, **kwargs)
        self.fields['request'].required = False

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['request']:
            return cleaned_data
        if not cleaned_data['distributor'] and cleaned_data['date'] and cleaned_data['request_name']:
            raise forms.ValidationError("Distributor, Date, and Request Name are required if no request is selected")
        if DistRequest.objects.filter(distributor=cleaned_data['distributor'],
                                      request_name=cleaned_data['request_name']).exists():
            self.add_error('request_name', "Request name already exists for this distributor")
        return cleaned_data

    def save(self, *args, **kwargs):
        partner = kwargs.pop('partner')
        product = kwargs.pop('product')
        print(self.cleaned_data['request'])
        if self.cleaned_data['request'] is None:
            self.cleaned_data['request'] = DistRequest.objects.create(request_name=self.cleaned_data['request_name'],
                                                                      distributor=self.cleaned_data['distributor'],
                                                                      date=self.cleaned_data['date'],
                                                                      partner=partner)
        saved_instance = super(DistRequestLineForm, self).save(commit=False)
        saved_instance.request = self.cleaned_data['request']
        saved_instance.partner = partner
        saved_instance.product = product
        saved_instance.save()
        return saved_instance
