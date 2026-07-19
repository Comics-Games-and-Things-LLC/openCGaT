from django.contrib import admin
from .models import BackorderReport, BackorderReportLine

class BackorderReportLineInline(admin.TabularInline):
    model = BackorderReportLine
    extra = 0

class BackorderReportAdmin(admin.ModelAdmin):
    list_display = ('distributor', 'retrieved')
    inlines = [BackorderReportLineInline]

admin.site.register(BackorderReport, BackorderReportAdmin)
