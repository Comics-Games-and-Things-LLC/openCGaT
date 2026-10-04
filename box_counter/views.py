from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from partner.models import get_partner_or_401
from .models import BoxInventory
from .forms import BoxInventoryForm

@login_required
def box_inventory(request, partner_slug):
    partner = get_partner_or_401(request, partner_slug)
    boxes = BoxInventory.objects.all()
    context = {
        'partner': partner,
        'boxes': boxes,
    }
    return render(request, "box_counter/box_inventory.html", context)

@login_required
def adjust_box_inventory(request, partner_slug, box_id):
    partner = get_partner_or_401(request, partner_slug)
    box = get_object_or_404(BoxInventory, id=box_id)
    if request.method == 'POST':
        form = BoxInventoryForm(request.POST, instance=box)
        if form.is_valid():
            form.save()
            return redirect('box_inventory', partner_slug=partner_slug)
    else:
        form = BoxInventoryForm(instance=box)
    context = {
        'partner': partner,
        'box': box,
        'form': form,
    }
    return render(request, "box_counter/adjust_box_inventory.html", context)
