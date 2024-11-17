import os

from dotenv import load_dotenv

from openCGaT.base import INSTALLED_APPS, AUTHENTICATION_BACKENDS
from openCGaT.components.ProjectPaths import ProjectPaths

load_dotenv(os.path.join(ProjectPaths.BASE_DIR, '.env'))

INSTALLED_APPS += (
    # The following apps are required:
    'django.contrib.sites',
    'django_recaptcha',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # ... include the providers you want to enable:
)
AUTHENTICATION_BACKENDS += (
    'allauth.account.auth_backends.AuthenticationBackend',
)

# Provider specific settings
SOCIALACCOUNT_PROVIDERS = {
}

ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_EMAIL_REQUIRED = True

ACCOUNT_AUTHENTICATION_METHOD = 'username_email'

# Setting this hopefully means logins will redirect to the page the user was on
ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = False

RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY', '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI')
RECAPTCHA_PRIVATE_KEY = os.getenv('RECAPTCHA_PRIVATE_KEY', '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe')
SILENCED_SYSTEM_CHECKS = ['django_recaptcha.recaptcha_test_key_error']

ACCOUNT_FORMS = {'signup': 'openCGaT.forms.AllAuthCaptchaSignupForm'}
