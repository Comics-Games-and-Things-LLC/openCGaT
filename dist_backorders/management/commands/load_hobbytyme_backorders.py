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
            self.process_partner(auth.partner, distributor, auth.username, auth.password)

    def process_partner(self, partner, distributor, username, password):
        self.stdout.write(f"Authenticating as {username} for partner {partner}...")

        session = requests.Session()
        # The base URL that redirects to login and provides the refresh key
        base_url = "https://hobbytyme.com/dealers/index.cfm"
        # The POST URL from the HAR
        login_post_url = "https://hobbytyme.com/dealers/index.cfm"
        
        # Headers from HAR to be more realistic
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        }
        
        try:
            # Step 1: GET the base page to establish session cookies and get refresh key via redirect
            self.stdout.write("Getting fresh refresh key from base page...")
            response = session.get(base_url, headers=headers)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Failed to get base page: {response.status_code}"))
                return
            
            soup = BeautifulSoup(response.text, 'html.parser')
            return_path_input = soup.find('input', {'name': 'returnPath'})
            refresh = None
            if return_path_input:
                value = return_path_input.get('value', '')
                refresh_match = re.search(r'refresh=(\d+)', value)
                if refresh_match:
                    refresh = refresh_match.group(1)
            
            if not refresh:
                # Fallback to regex on whole page
                refresh_match = re.search(r'refresh=(\d+)', response.text)
                if refresh_match:
                    refresh = refresh_match.group(1)

            if not refresh:
                self.stdout.write(self.style.ERROR("Could not find refresh key in page"))
                return
            
            self.stdout.write(f"Found refresh key: {refresh}")

            # Update headers with Referer for POST
            headers['Referer'] = response.url

            # Prepare credentials
            post_data = {
                'action': 'welcome',
                'returnPath': f'/dealers/index.cfm?refresh={refresh}&',
                'loginUsername': username,
                'loginPassword': password,
                'submit_btn': '.'
            }

            # Step 2: POST credentials to authenticate
            self.stdout.write("Posting credentials...")
            response = session.post(login_post_url, data=post_data, headers=headers)
            
            # After POST, it should redirect or show welcome page
            # We check if we are authenticated by checking if we can access the backorders page
            
            self.stdout.write("Fetching backorders table...")
            backorders_url = "https://hobbytyme.com/dealers/index.cfm?action=myAccount.backorders"
            response = session.get(backorders_url, headers=headers)
            
            if response.status_code == 200:
                if "loginPassword" in response.text:
                    self.stdout.write(self.style.ERROR("Login failed - still on login page"))
                    return

                soup = BeautifulSoup(response.text, 'html.parser')
                tables = soup.find_all('table')
                if not tables:
                    self.stdout.write(self.style.WARNING("No tables found on the page."))
                    return

                report = BackorderReport.objects.create(partner=partner, distributor=distributor)
                self.stdout.write(self.style.SUCCESS(f"Created report {report.id} for {partner}"))

                for i, table in enumerate(tables):
                    rows = table.find_all('tr')
                    if not rows:
                        continue
                    
                    header = [ele.text.strip() for ele in rows[0].find_all(['th', 'td'])]
                    
                    # Normalize header for matching
                    header_lower = [h.lower() for h in header]
                    
                    # Check if this is the backorders table
                    if not any(h in header_lower for h in ["item #", "part number"]):
                        continue
                    
                    self.stdout.write(self.style.SUCCESS(f"Processing backorders table..."))
                    
                    # Map header to indices with fallbacks
                    def get_index(names):
                        for name in names:
                            if name.lower() in header_lower:
                                return header_lower.index(name.lower())
                        return None

                    idx_mfc = get_index(["Manufacturer"])
                    idx_item = get_index(["Part Number", "Item #"])
                    idx_desc = get_index(["Product", "Description"])
                    idx_qty = get_index(["Qty", "Quantity"])
                    idx_price = get_index(["Price", "Unit Price"])
                    idx_date = get_index(["Date Ordered"])

                    if idx_item is None or idx_desc is None:
                        self.stdout.write(self.style.ERROR(f"Could not find required columns (Part Number and Product) in header: {header}"))
                        continue

                    for row in rows[1:]: # Skip header
                        cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
                        if len(cols) <= max(idx for idx in [idx_item, idx_desc, idx_price, idx_qty, idx_mfc, idx_date] if idx is not None):
                            continue
                        
                        try:
                            # Extract price
                            price_val = None
                            if idx_price is not None:
                                price_val = re.sub(r'[^\d.]', '', cols[idx_price]) or None

                            # Date Ordered parsing
                            date_ordered = None
                            if idx_date is not None:
                                date_str = cols[idx_date]
                                try:
                                    # Expected format: MM/DD/YYYY
                                    date_ordered = datetime.strptime(date_str, "%m/%d/%Y").date()
                                except ValueError:
                                    pass

                            line = BackorderReportLine(
                                report=report,
                                manufacturer=cols[idx_mfc] if idx_mfc is not None else None,
                                item_number=cols[idx_item],
                                description=cols[idx_desc],
                                unit_price=price_val,
                                quantity=int(cols[idx_qty] or 0) if idx_qty is not None else 0,
                                date_ordered=date_ordered,
                            )
                            line.set_product_from_item_number()
                            line.save()
                            self.stdout.write(f"Loaded {line.item_number} - {line.product}")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Error processing row {cols}: {e}"))
                
                self.stdout.write(self.style.SUCCESS(f"Finished loading backorders for {partner}."))
            else:
                self.stdout.write(self.style.ERROR(f'Failed to fetch backorders for {partner}: {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred for {partner}: {e}"))
