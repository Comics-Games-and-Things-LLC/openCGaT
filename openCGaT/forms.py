from allauth.account.forms import SignupForm
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3, ReCaptchaV2Checkbox


class AllAuthCaptchaSignupForm(SignupForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox(
    ))

    def save(self, request):
        user = super(AllAuthCaptchaSignupForm, self).save(request)
        return user
