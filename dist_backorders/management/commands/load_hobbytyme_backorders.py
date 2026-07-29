import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from dist_backorders.models import BackorderReport, BackorderReportLine
from intake.models import Distributor, PartnerDistAuth
from partner.models import Partner
from intake.distributors.hobbytyme import get_hobbytyme_session, DEFAULT_HEADERS, fetch_hobbytyme_pages, scrape_hobbytyme_tables

class Command(BaseCommand):
    help = 'Load backorders from Hobbytyme'

    def add_arguments(self, parser):
        parser.add_argument('--partner', type=str, help='Partner slug to load backorders for')

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
            self.process_partner(auth)

    def process_partner(self, auth):
        partner = auth.partner
        distributor = auth.distributor
        self.stdout.write(f"Authenticating as {auth.username} for partner {partner}...")

        session = get_hobbytyme_session(auth)
        if not session:
            self.stdout.write(self.style.ERROR(f"Failed to authenticate as {auth.username}"))
            return

        headers = DEFAULT_HEADERS.copy()

        try:
            backorders_url = "https://hobbytyme.com/dealers/index.cfm?action=myAccount.backorders"
            
            report = None

            for soup, current_url in fetch_hobbytyme_pages(session, backorders_url, headers):
                if "loginPassword" in soup.text:
                    self.stdout.write(self.style.ERROR("Login failed - still on login page"))
                    return

                if not report:
                    report = BackorderReport.objects.create(partner=partner, distributor=distributor)
                    self.stdout.write(self.style.SUCCESS(f"Created report {report.id} for {partner}"))

                self.stdout.write(f"Processing backorders from {current_url}...")
                
                for data in scrape_hobbytyme_tables(soup):
                    try:
                        # Extract price
                        msrp = None
                        if data['msrp']:
                            msrp = re.sub(r'[^\d.]', '', data['msrp']) or None

                        # Date Ordered parsing
                        date_ordered = None
                        if data['orders_due']:
                            try:
                                date_ordered = datetime.strptime(data['orders_due'], "%m/%d/%Y").date()
                            except ValueError:
                                pass

                        line = BackorderReportLine(
                            report=report,
                            manufacturer=data['manufacturer'],
                            item_number=data['item_number'],
                            description=data['description'],
                            msrp=msrp,
                            quantity=int(data['quantity'] or 0) if data['quantity'] is not None else 0,
                            date_ordered=date_ordered,
                        )
                        line.set_product_from_item_number()
                        line.save()
                        self.stdout.write(f"Loaded {line.item_number} - {line.product}")
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing data {data}: {e}"))
            
            if report:
                self.stdout.write(self.style.SUCCESS(f"Finished loading backorders for {partner}."))
            else:
                self.stdout.write(self.style.WARNING(f"No backorders found for {partner}."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred for {partner}: {e}"))
