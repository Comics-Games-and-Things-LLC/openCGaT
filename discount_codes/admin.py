from django.contrib import admin

from checkout.admin import HasCartAdmin
from .models import DiscountCode, Referrer, PartnerDiscount, CodeUsage, URLShortener

# Register your models here.
admin.site.register(DiscountCode)
admin.site.register(Referrer)
admin.site.register(PartnerDiscount)
admin.site.register(CodeUsage)


class CodeUsageAdmin(HasCartAdmin):
    autocomplete_fields = ['cart', 'user']


admin.site.register(CodeUsage, CodeUsageAdmin)
