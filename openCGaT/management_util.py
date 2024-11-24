from django.conf import settings
from django.core.mail import EmailMessage


def email_report(report_name, file_list):
    if settings.DEBUG:
        report_name = f"(DEV) {report_name}"
    email = EmailMessage(report_name,
                         "Attached is the report",
                         to=[settings.EMAIL_HOST_USER])
    if type(file_list) is str:
        file_list = [file_list]
    for filename in file_list:
        email.attach_file(filename)
    email.send()
    print(f"Emailed to {settings.EMAIL_HOST_USER}")
