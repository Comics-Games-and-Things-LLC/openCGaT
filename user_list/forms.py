from django import forms

from user_list.models import UserList


class UserListCSVImportForm(forms.ModelForm):
    csv_input = forms.CharField(widget=forms.Textarea())

    class Meta:
        model = UserList
        fields = ['csv_input']

    def save(self, *args, **kwargs):
        partner = kwargs.pop('partner')
        saved_instance = super(UserListCSVImportForm, self).save(*args, **kwargs)
        csv_data = self.cleaned_data['csv_input']
        print(csv_data)
        if csv_data:
            for email in csv_data.split(","):
                print(email)
                saved_instance.import_entry(email)
        saved_instance.partner = partner
        saved_instance.save()
        return saved_instance


class UserListForm(UserListCSVImportForm):
    class Meta:
        model = UserList
        fields = ['name', 'description', 'csv_input']
