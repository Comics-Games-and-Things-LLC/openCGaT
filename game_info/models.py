from django.db import models

# Create your models here.
from django.utils.text import slugify
from djmoney.models.fields import MoneyField
from wagtail.fields import RichTextField


class Game(models.Model):
    name = models.TextField()
    publisher = models.ForeignKey('shop.Publisher', on_delete=models.SET_NULL, null=True, blank=True)
    description = RichTextField(blank=True, null=True, features=['h2', 'h3', 'bold', 'italic', 'ol', 'ul'])
    cost_to_start = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True, default_currency='USD')
    approximate_cost_of_full_force = MoneyField(max_digits=19, decimal_places=2, null=True, blank=True,
                                                default_currency='USD')

    featured = models.BooleanField(default=False)
    navbar_order = models.IntegerField(null=True, blank=True,
                                       help_text="If populated, will appear in navbar, highest first")

    slug = models.SlugField(blank=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)

        super(Game, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    def root_factions(self):
        return self.factions.filter(subfaction_of=None)

    def get_sorted_attributes(self):
        attributes = {}
        for at in self.attribute_types.all():
            attributes[at] = self.attributes.filter(type=at)
        return attributes


class Edition(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='editions')
    name = models.TextField()
    description = RichTextField(blank=True, null=True, features=['h2', 'h3', 'bold', 'italic', 'ol', 'ul'])

    def __str__(self):
        return "{} {}".format(self.game, self.name)


class Format(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='formats')
    name = models.TextField()
    description = RichTextField(blank=True, null=True, features=['h2', 'h3', 'bold', 'italic', 'ol', 'ul'])

    def __str__(self):
        return "{} {}".format(self.game, self.name)


class Faction(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='factions')
    subfaction_of = models.ForeignKey('Faction', on_delete=models.CASCADE, null=True, blank=True,
                                      related_name='subfactions')
    name = models.TextField()
    description = RichTextField(blank=True, null=True, features=['h2', 'h3', 'bold', 'italic', 'ol', 'ul'])

    subfaction_models_not_in_parent_faction = models.BooleanField(default=False)

    slug = models.SlugField(blank=True, null=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Faction, self).save(*args, **kwargs)

    def __str__(self):
        return "{} {}".format(self.game, self.name)

    def get_sorted_attributes(self):
        attributes = {}
        for at in self.game.attribute_types.all():
            attributes[at] = self.attributes.filter(type=at)
        return attributes


class AttributeType(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='attribute_types')
    name = models.TextField()


class Attribute(models.Model):
    """Colors, Keywords, etc"""
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='attributes')
    factions = models.ManyToManyField(Faction, related_name='attributes', blank=True)
    type = models.ForeignKey(AttributeType, on_delete=models.CASCADE, related_name='attributes')

    name = models.TextField()
    description = RichTextField(blank=True, null=True, features=['h2', 'h3', 'bold', 'italic', 'ol', 'ul'])

    def __str__(self):
        return "{} {}".format(self.game, self.name)


class GamePiece(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='piece')
    name = models.TextField()
    factions = models.ManyToManyField('Faction')
    attributes = models.ManyToManyField('Attribute')

    # At some point we will add model options. But for now, there's just a model.


class GamePieceVariant(models.Model):
    """ eg specific loadout"""
    piece = models.ForeignKey(GamePiece, on_delete=models.CASCADE, related_name='variants')
    attributes = models.ManyToManyField('Attribute', blank=True)


class ContainsPieces(models.Model):
    product = models.ForeignKey("shop.Product", on_delete=models.CASCADE, related_name="contains_pieces")
    quantity = models.PositiveIntegerField()
    of = models.ForeignKey(GamePieceVariant, on_delete=models.CASCADE, blank=True, null=True,
                           related_name="contained_in")
    any_of = models.ManyToManyField(GamePieceVariant, blank=True, related_name="contained_in_option")
