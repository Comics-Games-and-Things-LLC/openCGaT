from django.contrib import admin

from .models import *


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'publisher', 'featured', 'navbar_order')
    list_filter = ('featured', 'publisher')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)


@admin.register(Format)
class FormatAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    list_filter = ('game',)
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(Faction)
class FactionAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'subfaction_of')
    list_filter = ('game', 'subfaction_of')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    list_filter = ('game',)
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'type')
    list_filter = ('game', 'type', 'factions')
    search_fields = ('name', 'description')
    filter_horizontal = ('factions',)
    ordering = ('name',)


@admin.register(AttributeType)
class AttributeTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'game')
    list_filter = ('game',)
    search_fields = ('name',)
    ordering = ('name',)
