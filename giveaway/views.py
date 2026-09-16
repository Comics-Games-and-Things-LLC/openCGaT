import datetime

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render

# Create your views here.
from django.template.response import TemplateResponse
from django.urls import reverse

from giveaway.models import Giveaway, Entry


def giveaways(request):
    context = {'list': Giveaway.objects.filter(end_time__gte=datetime.datetime.now())}
    return TemplateResponse(request, "giveaways/giveaways.html", context=context)


def enter_giveaway(request, giveaway_id):
    if request.user.is_authenticated:
        entry, created = Entry.objects.get_or_create(user=request.user, giveaway_id=giveaway_id)
        entry.save()
    return HttpResponseRedirect(reverse('giveaways'))

