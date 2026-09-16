from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from partner.models import get_partner_or_401
from .models import PrintQueueItem


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
