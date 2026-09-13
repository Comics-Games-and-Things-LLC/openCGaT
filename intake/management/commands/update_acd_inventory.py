from django.core.management.base import BaseCommand
from intake.models import Distributor, PartnerDistAuth
from partner.models import Partner
from intake.distributors.acd import update_inventory


class Command(BaseCommand):
    help = 'Update inventory from ACD'

    def add_arguments(self, parser):
        parser.add_argument('--partner', type=str, help='Partner slug to update inventory for', required=False)

    def handle(self, *args, **options):
        partner_slug = options.get('partner')

        distributor = Distributor.objects.filter(dist_name="ACD").first()

        auth = None
        if partner_slug and distributor:
            try:
                partner = Partner.objects.get(slug=partner_slug)
                auth = PartnerDistAuth.objects.filter(partner=partner, distributor=distributor).first()
            except Partner.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Partner with slug '{partner_slug}' not found."))
                return

        self.stdout.write("Updating inventory for ACD...")
        try:
            update_inventory(auth)
            self.stdout.write(self.style.SUCCESS("Finished updating inventory for ACD."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred updating ACD inventory: {e}"))
