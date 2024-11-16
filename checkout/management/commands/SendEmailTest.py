import csv
import datetime

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from checkout.models import Cart


class Command(BaseCommand):
    def handle(self, *args, **options):
        email = EmailMessage("Email sending test",
                             "Can the server send email? Or is it just blocking specific emails?",
                             to=[settings.EMAIL_HOST_USER])
        email.send()