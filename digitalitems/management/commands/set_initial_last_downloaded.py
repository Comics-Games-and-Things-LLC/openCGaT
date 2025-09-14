from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

import digitalitems
from digitalitems.models import DIFile, DigitalItem, DownloadHistory, UserDownloadableHistory, Downloadable


class Command(BaseCommand):

    def handle(self, *args, **options):
        print("Updating Downloadables")
        files = DIFile.objects.all()
        file_count = files.count()
        i = 0
        for file in files:
            file.save()  # Should update each downloadable (and it's parents) with the upload date of each file.
            i += 1
            print("Processed {}/{} files".format(
                i, file_count),
                end="\r",
                flush=True)


        print("\nCreating History")
        history = DownloadHistory.objects.all()
        count = history.count()
        i = 0
        for download in history:
            timestamp = download.timestamp
            if hasattr(download.file, "downloadable"):
                downloadable = download.file.downloadable
                user = download.user
                for ancestor in downloadable.get_ancestors():
                    an_timestamp = None
                    try:
                        an_timestamp = ancestor.download_history.filter(user=user).latest().timestamp
                    except UserDownloadableHistory.DoesNotExist:
                        pass
                    if an_timestamp and an_timestamp <= timestamp:
                        new_entry = ancestor.download_history.create(user=user)
                        new_entry.timestamp = timestamp
                        new_entry.save()
                new_entry = downloadable.download_history.create(user=user)
                new_entry.timestamp = timestamp
                new_entry.save()
            i += 1
            print("Processed {}/{} download histories".format(
                i, count),
                end="\r",
                flush=True)
