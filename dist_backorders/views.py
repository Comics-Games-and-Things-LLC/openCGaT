from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import BackorderReport
from partner.models import Partner
from .forms import FiltersForm

def hobbytyme_backorder_report(request, partner_slug, report_id=None):
    partner = get_object_or_404(Partner, slug=partner_slug)
    if report_id:
        report = get_object_or_404(BackorderReport, id=report_id, partner=partner, distributor__dist_name="Hobbytyme")
    else:
        report = BackorderReport.objects.filter(partner=partner, distributor__dist_name="Hobbytyme").order_by('-retrieved').first()
    
    reports = BackorderReport.objects.filter(partner=partner, distributor__dist_name="Hobbytyme").order_by('-retrieved')
    
    # Simple previous/next navigation
    previous_report = None
    next_report = None
    if report:
        previous_report = reports.filter(retrieved__lt=report.retrieved).first()
        next_report = reports.filter(retrieved__gt=report.retrieved).last()

    return render(request, 'dist_backorders/hobbytyme_report.html', {
        'report': report, 
        'partner': partner,
        'previous_report': previous_report,
        'next_report': next_report,
    })

def hobbytyme_backorder_list(request, partner_slug):
    partner = get_object_or_404(Partner, slug=partner_slug)
    reports = BackorderReport.objects.filter(partner=partner, distributor__dist_name="Hobbytyme").order_by('-retrieved')
    
    form = FiltersForm(request.GET)
    if form.is_valid():
        search = form.cleaned_data.get('search')
        if search:
            reports = reports.filter(retrieved__icontains=search)

    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)
    
    return render(request, 'dist_backorders/hobbytyme_report_list.html', {
        'page': page, 
        'partner': partner,
        'filters_form': form,
    })
