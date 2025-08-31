import datetime

from django.core.validators import URLValidator
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import InlinePanel, FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page, Orderable
from wagtail.search import index

# Create your models here.
from shop.models import Item, Product


class HomePage(Page):
    content_panels = Page.content_panels + [
        InlinePanel('carousel_items', label="Carousel items"),
        InlinePanel('feature_columns', label="Feature columns")
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        visible_products = Product.objects.filter_listed()
        visible_items = Item.objects.filter(product__in=visible_products)

        if hasattr(request, 'site') and hasattr(request.site, 'partner'):
            partner = request.site.partner
            visible_items = visible_items.filter(partner=partner)
            context['carousel_items'] = self.carousel_items.filter(partner=partner)
            context['feature_columns'] = self.feature_columns.filter(partner=partner)

        else:
            context['carousel_items'] = self.carousel_items.filter(partner_only=False)
            context['feature_columns'] = self.feature_columns.filter(partner__isnull=True)

        featured_items = visible_items.filter(featured=True).order_by('-product__release_date')

        context['recent_arrivals'] = visible_items \
                                         .exclude(inventoryitem__last_stocked_time__isnull=True) \
                                         .exclude(inventoryitem__isnull=True) \
                                         .order_by('-inventoryitem__last_stocked_time')[0:5]

        context['featured_new_releases'] = featured_items \
                                      .exclude(product__release_date__gt=datetime.date.today()) \
                                      .exclude(inventoryitem__current_inventory=0)[0:5]

        context['featured_items'] = featured_items[0:5]

        return context


class HomePageCarousel(Orderable):
    page = ParentalKey(HomePage, on_delete=models.CASCADE, related_name='carousel_items')
    body = RichTextField()
    cover_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    button_text = models.CharField(max_length=255, blank=True)
    button_link = models.CharField(max_length=512,
                                   blank=True,
                                   validators=[URLValidator(schemes=['http', 'https', 'ftp', 'ftps', 'mailto'])]
                                   )
    alignment = models.CharField(max_length=6,
                                 choices=[
                                     ('left', "Left aligned"),
                                     ('center', "Centered"),
                                     ('right', "Right aligned")
                                 ],
                                 default='left')
    partner = models.ForeignKey('partner.Partner', on_delete=models.CASCADE, null=True, blank=True)
    partner_only = models.BooleanField(default=False)

    panels = [
        FieldPanel('body'),
        FieldPanel('cover_image'),
        FieldPanel('button_text'),
        FieldPanel('button_link'),
        FieldPanel('alignment'),
        FieldPanel('partner'),
        FieldPanel('partner_only'),
    ]


class HomePageFeatureColumn(Orderable):
    page = ParentalKey(HomePage, on_delete=models.CASCADE, related_name='feature_columns')
    body = RichTextField()
    partner = models.ForeignKey('partner.Partner', on_delete=models.CASCADE, null=True, blank=True)

    panels = [
        FieldPanel('body'),
        FieldPanel('partner'),
    ]


class CGTPage(Page):
    body = RichTextField()

    search_fields = Page.search_fields + [
        index.SearchField('body'),
    ]

    content_panels = Page.content_panels + [
        FieldPanel('body', classname="full"),
    ]
