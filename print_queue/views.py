import json
import time

from django.db import transaction, models
from django.db.models import Q
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from partner.models import get_partner_or_401
from .models import PrintQueueItem, Printer, PrintJob


class PrintQueueListView(LoginRequiredMixin, ListView):
    model = PrintQueueItem
    template_name = 'print_queue/queue.html'
    context_object_name = 'queue_items'

    def dispatch(self, request, *args, **kwargs):
        self.partner = get_partner_or_401(request, self.kwargs['partner_slug'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return PrintQueueItem.objects.filter(inventory_item__partner=self.partner, restickered=False).order_by('created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['partner'] = self.partner
        return context


@require_POST
def mark_printed(request, partner_slug, item_id):
    partner = get_partner_or_401(request, partner_slug)
    item = get_object_or_404(PrintQueueItem, id=item_id, inventory_item__partner=partner)
    item.printed = True
    item.printed_at = timezone.now()
    item.quantity_at_printing = item.inventory_item.current_inventory
    item.save()
    return JsonResponse({
        'status': 'success',
        'quantity_at_printing': item.quantity_at_printing,
        'current_inventory': item.inventory_item.current_inventory
    })


@require_POST
def mark_restickered(request, partner_slug, item_id):
    partner = get_partner_or_401(request, partner_slug)
    item = get_object_or_404(PrintQueueItem, id=item_id, inventory_item__partner=partner)
    item.restickered = True
    item.restickered_at = timezone.now()
    item.save()
    return JsonResponse({'status': 'success'})


@require_POST
def mark_all_restickered(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    PrintQueueItem.objects.filter(inventory_item__partner=partner, restickered=False).update(
        restickered=True,
        restickered_at=timezone.now()
    )
    return JsonResponse({'status': 'success'})


mark_all_finished = mark_all_restickered


@require_POST
def register_printer(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    client_id = request.POST.get('client_id')
    name = request.POST.get('name')
    if not client_id:
        return JsonResponse({'error': 'client_id is required'}, status=400)

    printer, created = Printer.objects.update_or_create(
        partner=partner,
        client_id=client_id,
        defaults={'name': name, 'last_seen': timezone.now()}
    )
    return JsonResponse({'status': 'success', 'client_id': printer.client_id})


def get_online_printers(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    # Consider printers seen in the last 2 minutes as online
    threshold = timezone.now() - timezone.timedelta(minutes=2)
    printers = Printer.objects.filter(partner=partner, last_seen__gte=threshold)
    return JsonResponse({
        'printers': [{'client_id': p.client_id, 'name': p.name} for p in printers]
    })


@require_POST
def add_print_job(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    data = json.loads(request.body)
    job_type = data.get('job_type')
    payload = data.get('payload')
    destination_client_id = data.get('destination_client_id')

    destination_printer = None
    if destination_client_id:
        destination_printer = Printer.objects.filter(partner=partner, client_id=destination_client_id).first()

    job = PrintJob.objects.create(
        partner=partner,
        destination_printer=destination_printer,
        job_type=job_type,
        payload=payload,
        status='PENDING'
    )
    return JsonResponse({'status': 'success', 'job_id': job.id})


@require_POST
def claim_print_job(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    data = json.loads(request.body)
    client_id = data.get('client_id')
    job_id = data.get('job_id')

    with transaction.atomic():
        # Find jobs for this partner, either unassigned or assigned to this client
        jobs = PrintJob.objects.select_for_update().filter(
            partner=partner,
            status='PENDING'
        ).filter(
            Q(destination_printer__isnull=True) | Q(destination_printer__client_id=client_id)
        )
        if job_id:
            jobs = jobs.filter(id=job_id)

        job = jobs.order_by('created_at').first()
        if job:
            job.status = 'CLAIMED'
            job.save()
            return JsonResponse({
                'status': 'success',
                'job': {
                    'id': job.id,
                    'job_type': job.job_type,
                    'payload': job.payload
                }
            })

    return JsonResponse({'status': 'no_jobs'}, status=204)


@require_POST
def mark_job_printed(request, partner_slug, job_id):
    partner = get_partner_or_401(request, partner_slug)
    job = get_object_or_404(PrintJob, id=job_id, partner=partner)
    job.status = 'PRINTED'
    job.save()
    return JsonResponse({'status': 'success'})


def print_job_stream(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    client_id = request.GET.get('client_id')

    def event_stream():
        # Start by finding the latest job ID so we only notify about new ones
        last_job_id = PrintJob.objects.filter(partner=partner).order_by('-id').values_list('id', flat=True).first() or 0
        while True:
            new_jobs = PrintJob.objects.filter(
                partner=partner,
                status='PENDING',
                id__gt=last_job_id
            ).filter(
                Q(destination_printer__isnull=True) | Q(destination_printer__client_id=client_id)
            ).order_by('id')

            for job in new_jobs:
                yield f"data: {json.dumps({'event': 'NEW_JOB', 'job_id': job.id})}\n\n"
                last_job_id = job.id

            yield ": heartbeat\n\n"
            time.sleep(5)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response
