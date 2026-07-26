from django.core.management.base import BaseCommand
from intake.models import Distributor, PartnerDistAuth
from partner.models import Partner
from intake.distributors.hobbytyme import update_inventory

class Command(BaseCommand):
    help = 'Update inventory from Hobbytyme'

    def add_arguments(self, parser):
        parser.add_argument('--partner', type=str, help='Partner slug to update inventory for')

    def handle(self, *args, **options):
        partner_slug = options.get('partner')
        
        distributor = Distributor.objects.get(dist_name="Hobbytyme")
        
        if partner_slug:
            try:
                partner = Partner.objects.get(slug=partner_slug)
                auths = PartnerDistAuth.objects.filter(partner=partner, distributor=distributor)
            except Partner.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Partner with slug '{partner_slug}' not found."))
                return
        else:
            auths = PartnerDistAuth.objects.filter(distributor=distributor)
        
        if not auths.exists():
            self.stdout.write(self.style.WARNING(f"No authentication credentials found for Hobbytyme in PartnerDistAuth model."))
            return

        for auth in auths:
            self.stdout.write(f"Updating inventory for partner {auth.partner} as {auth.username}...")
            try:
                update_inventory(auth)
                self.stdout.write(self.style.SUCCESS(f"Finished updating inventory for {auth.partner}."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"An error occurred for {auth.partner}: {e}"))
