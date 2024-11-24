import io
import os
import urllib
from urllib.parse import urlparse

from django.db import models

from images.PublicAzureStorage import PublicAzureStorage
from partner.models import Partner


# from imagekit.models import ImageSpecField
# from pilkit.processors import ResizeToFit


class Image(models.Model):
    image_src = models.ImageField(upload_to='images', storage=PublicAzureStorage)
    # These did not use the correct storage, and I'm not sure that they support alternate storage. As such I've removed them.
    # banner_full = ImageSpecField(source='image_src',
    #                              processors=[ResizeToFit(1800, 480)],
    #                              options={'quality': 60})
    # product_gallery_thumb = ImageSpecField(source='image_src',
    #                                        processors=[ResizeToFit(100, 100)],
    #                                        options={'quality': 60},
    #                                        cachefile_storage=PublicAzureStorage
    #                                        )

    alt_text = models.CharField(max_length=200, blank=True, null=True,
                                help_text="Used in screen readers for the visually impared. " +
                                          " Blank to default to filename")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, blank=True, null=True)

    def __str__(self):
        return "{} image ({}) from {}".format(self.alt_text, self.id, self.partner)

    def save(self, *args, **kwargs):
        if not self.alt_text:
            # Set alt text to the filename, without the extension, and replace underscores with spaces
            self.alt_text = ".".join(self.image_src.name.split('.')[:-1]).replace('_', ' ')
        return super(Image, self).save(*args, **kwargs)

    class Meta:
        ordering = ['id']  # Order by ID which is roughly equivalent to upload order.

    @property
    def image(self):
        return self.image_src
        # used to maintain compatibility with older templates.

    @property
    def image_url(self):
        if self.image and hasattr(self.image_src, 'url'):
            return self.image.url

    @staticmethod
    def create_from_external_url(url, alt_text=None):
        parsed_url = urlparse(url)
        filename = os.path.splitext(os.path.basename(parsed_url.path))[0]
        print(filename)
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        image = None
        with urllib.request.urlopen(url) as image_file:
            image = Image.objects.create()
            image.image_src.save(filename, io.BytesIO(image_file.read()))
            if alt_text:
                image.alt_text = alt_text
            else:
                image.alt_text = filename.replace("_", " ").replace("-", " ")
            image.save()

        return image
