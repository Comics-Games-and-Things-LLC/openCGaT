import hashlib
import os
from datetime import datetime

from azure.common import AzureMissingResourceHttpError
from dateutil import tz
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import models
# Create your models here.
from django.db.models import UniqueConstraint, Q
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from digitalitems.azure_storage import PrivateAzureStorage
from partner.models import Partner
from shop.models import Item


class Downloads(models.Model):
    item = models.ForeignKey('DigitalItem', on_delete=models.CASCADE, related_name='downloads')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='downloads')
    date = models.DateTimeField()
    partner_paid = models.BooleanField(default=False)
    added_from_cart = models.ForeignKey('checkout.Cart', on_delete=models.PROTECT, null=True)

    timestamp_added = models.DateTimeField(
        auto_now_add=True, blank=True,
        null=True)  # May differ from date as date will often be from pledge or cart purchase.
    # Null values are from before the value was added to the database

    skip_billing = models.BooleanField(default=False)  # Skip billing events before campaign billing start date
    billing_event = models.ForeignKey("billing.BillingEvent", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.email + " " + str(self.item) + " " + str(self.date) + " (" + str(self.id) + ")"

    class Meta:
        constraints = [
            models.constraints.UniqueConstraint(fields=['user', 'item'], name='one_purchase_record_per_user')
        ]


class DigitalItem(Item):
    artist = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    derived_from_all = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='derivatives_all')
    derived_from_any = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='derivatives_any')
    download_date = models.DateField('Date Available for download')
    files = models.ManyToManyField('DIFile', blank=True)
    root_downloadable = models.ForeignKey('Downloadable', on_delete=models.SET_NULL, null=True, blank=True)
    # date_files_last_updated = get from root downloadable now
    pay_what_you_want = models.BooleanField(default=False,
                                            help_text="This makes price the minimum the user has to pay, "
                                                      "and default price the amount the form defaults to")
    enable_download_all = models.BooleanField(default=True, help_text="Show the Download All Button")

    max_per_cart = 1

    def save(self, *args, **kwargs):
        if self.root_downloadable is None:
            self.root_downloadable = Downloadable.objects.create(folder=self.product.slug)
        else:
            self.root_downloadable.folder = self.product.slug
            self.root_downloadable.save()
        super().save(*args, **kwargs)

    def available_for_download(self):
        if self.download_date <= datetime.utcnow().astimezone(tz=tz.tzutc()).date():
            return True
        else:
            return False

    def download_overlay_banner(self, user):
        """
        Gets banner status and if the user can download the files.
        :return: any banner to appear over the file (new, updated)
        """
        banner = None
        if self.available_for_download() and user.is_authenticated:
            can_download = self.downloads.filter(user=user).exists()  # Fixed duplicate purchases causing errors
            if can_download and self.root_downloadable:
                history = self.root_downloadable.download_history.filter(user=user)
                if history.exists() and history.first().timestamp <= self.root_downloadable.updated_timestamp:
                    banner = "Updated"
                else:
                    banner = "New"
        return banner

    def get_total_derivative_price(self, prevent_loop_id=None):
        if prevent_loop_id is None:
            prevent_loop_id = []
        prevent_loop_id.append(self.id)
        price = self.price
        for item in self.derived_from_all.exclude(id__in=prevent_loop_id):
            price += item.get_total_derivative_price(prevent_loop_id=prevent_loop_id)
        pass
        price += self.get_cheapest_deriv_any_price(prevent_loop_id=prevent_loop_id)
        return price

    def get_cheapest_deriv_any_price(self, prevent_loop_id=None):
        if prevent_loop_id is None:
            prevent_loop_id = []
        prevent_loop_id.append(self.id)
        price = self.price
        for item in self.derived_from_any.exclude(id__in=prevent_loop_id):
            item_price = item.get_total_derivative_price(prevent_loop_id=prevent_loop_id)
            if item_price < price:
                price = item_price
        return price

    def is_free(self):
        if self.get_total_derivative_price() == 0:
            return True

    def deriv_qualify_for_purchase(self, cart=None):
        if (not self.derived_from_all.exists()) and (not self.derived_from_any.exists()):
            return True  # Not a derivative, so qualifies for purchase
        # If cart is none we have to return false as we won't be able to load the cart or user.
        if cart is None:
            return False
        user = None
        if cart.owner:  # The item can stay in the cart if there's no owner as long as the prerequs are in the cart.
            user = cart.owner
        # Return false if any of the all items are not purchased/in cart
        for item in self.derived_from_all.exclude(id=self.id):
            if not Downloads.objects.filter(user=user, item=item).exists() \
                    and not (cart and cart.lines.filter(item=item).exists()):
                return False

        # Return true if any of these items are purchased/in cart
        if self.derived_from_any.exists():
            for item in self.derived_from_any.exclude(id=self.id):
                if Downloads.objects.filter(user=user, item=item).exists() \
                        or (cart and cart.lines.filter(item=item).exists()):
                    return True
            return False  # if none of the any items are purchased, return false
        # returns true if we don't return false at the "all" step or
        return True

    def cart_owner_allowed_to_purchase(self, cart):
        return self.deriv_qualify_for_purchase(cart)

    def button_status(self, cart=None):
        if self.cart_owner_allowed_to_purchase(cart):
            return super().button_status(cart)
        else:
            return {'text': "Requires other items", 'enabled': False, "style": self.BUTTON_STYLE_SOLD_OUT}

    def user_already_owns(self, user):
        return not user.is_anonymous and len(self.downloads.filter(user=user)) > 0

    def purchase(self, cart):
        download_instance, created = self.downloads.get_or_create(user=cart.owner,
                                                                  defaults={"date": cart.date_submitted,
                                                                            "added_from_cart": cart})
        if not created:
            msg = EmailMessage(subject='Duplicate Item Purchased: {}'.format(self.id),
                               body="""
                                           {} purchased {} in {} which was already in their downloads. 
                                           This email could be a mistake and should be manually checked
                                           """.format(cart.owner, self, cart.id),
                               from_email=None,
                               to=["nsh@comicsgamesandthings.com"])
            msg.content_subtype = 'html'
            msg.send(fail_silently=True)

            print("{} purchased {} which they already own".format(cart.owner, self))


def get_upload_hash_path(self, filename):
    # https://stackoverflow.com/questions/31731470/efficiently-saving-a-file-by-hash-in-django/41906536
    self.azure_file.open()  # make sure we're at the beginning of the file
    contents = self.azure_file.read()  # get the contents
    fname, ext = os.path.splitext(filename)
    m = hashlib.md5()
    m.update(contents)
    return "downloads/{}/{}_{}/{}".format(self.partner, fname, m.hexdigest(), filename)  # assemble the filename


class DIFile(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True)
    clean_name = models.CharField(max_length=200, blank=True, null=True)
    torrent_file = models.FileField(upload_to='media/', max_length=500, blank=True, null=True)
    b2_file = models.FileField(upload_to='media/', max_length=500)
    azure_file = models.FileField(upload_to=get_upload_hash_path, max_length=500, storage=PrivateAzureStorage,
                                  null=True)

    preview_image = models.ImageField(upload_to='media/', max_length=500, blank=True, null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    file_size = models.IntegerField()

    @property
    def server_file(self):
        return self.azure_file

    def __str__(self):
        name = ""
        if self.clean_name:
            name += str(self.clean_name)
        else:
            name += str(self.server_file.name)
        return name

    def save(self, *args, **kwargs):
        try:
            if self.clean_name.index('/') >= 0:
                self.clean_name = self.clean_name.split("/")[-1]
        except ValueError:
            pass
        if self.azure_file:
            try:
                self.file_size = self.azure_file.size
            except AzureMissingResourceHttpError:
                pass
        else:
            self.file_size = self.b2_file.size
        if hasattr(self, 'downloadable'):
            self.downloadable.save()  # Update last upload date, etc
        super(DIFile, self).save(*args, **kwargs)

    def log_download(self, user):
        """
        Called by the download script to create a timestamp, and update the downloadable for the history.
        :param user: the user (from request.user)
        :return: None
        """
        history = self.download_history.create(user=user)
        self.downloadable.log_download(user)
        return history


class Downloadable(MPTTModel):
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    folder = models.CharField(max_length=200, null=True, blank=True)
    file = models.OneToOneField(DIFile, on_delete=models.CASCADE, null=True, related_name='downloadable')
    updated_timestamp = models.DateTimeField(default=datetime.now)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['parent', 'folder'], condition=Q(file=None), name='unique_folder'),
            # Ignore this constraint when the folder is None (as file will be none).
        ]

    def save(self, *args, **kwargs):
        if self.file:
            self.updated_timestamp = self.file.upload_date
        if self.parent:
            self.parent.updated_timestamp = self.updated_timestamp
            self.parent.save()
        super(Downloadable, self).save(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if (not cleaned_data.get('folder') and not cleaned_data.get('file')) \
                or (cleaned_data.get('folder') and cleaned_data.get('file')):
            raise ValidationError("Folder or file must be set, but not both")

    def get_download_info(self, path=""):
        files_to_download = []
        if self.folder:
            path += self.folder + "/"
        for child in self.get_children():
            if child.folder:
                files_to_download += child.get_download_info(path=path)
            if child.file:
                filename = child.file.clean_name.split("/")[-1]
                files_to_download.append({'download_as': path + filename,
                                          'id': child.file.id,
                                          'size': child.file.file_size,
                                          'filename': filename
                                          })

        return files_to_download

    def follow_or_create_path(self, path):
        try:
            index = path.index('/')
            folder_name = path[:index]
            new_path = path[index + 1:]
            node, created = self.get_children().select_for_update().get_or_create(folder=folder_name, parent=self)
            if created:
                node.save()
            return node.follow_or_create_path(new_path)

        except ValueError:
            return self

    def cascading_delete(self):
        for child in self.get_children():
            child.cascading_delete()
        if self.file:
            self.file.delete()
        self.delete()

    def __str__(self):
        if self.folder:
            return "Folder: {} ({})".format(self.folder, self.id)
        if self.file:
            return "File: {} ({})".format(self.file.clean_name, self.id)

    def log_download(self, user):
        """
        Called by the individual file to update the parent folders and eventually the root downloadable.
        :param user: the user (from request.user)
        :return: None
        """
        for parent in self.get_ancestors():
            # There should never be a situation where this happens in the past,
            # so we don't need to check which date is most recent.
            parent.download_history.create(user=user)
        self.download_history.create(user=user)

    def create_dict(self, user):
        """
        Old Proto-serializer. Depreciated
        :param user:
        :return:
        """
        from digitalitems.serializers import DIFileSerializer
        folder_dict = {'metadata': self.id}
        for child in self.get_children():
            if child.folder:
                folder_dict[child.folder] = child.create_dict(user=user)
            if child.file:
                folder_dict[child.file.clean_name.split("/")[-1]] = DIFileSerializer(child.file,
                                                                                     context={'user': user}).data
        return folder_dict


class UserDownloadableHistory(models.Model):
    """
    This is a record of every time a user has downloaded a file, folder, or any file in that folder.
    Used to inform the user on if a download is new.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="downloadable_history")
    downloadable = models.ForeignKey(Downloadable, on_delete=models.CASCADE, related_name="download_history")
    timestamp = models.DateTimeField(default=datetime.now)

    class Meta:
        get_latest_by = "timestamp"
        indexes = [
            models.Index(fields=['user', 'downloadable']),
        ]


class DownloadHistory(models.Model):
    """
    This is a record of every time the user has downloaded a file
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="download_history")
    file = models.ForeignKey(DIFile, on_delete=models.CASCADE, related_name="download_history")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        get_latest_by = "timestamp"
        indexes = [
            models.Index(fields=['user', 'file']),
        ]
