import os
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Load backorders from Hobbytyme'

    def handle(self, *args, **options):
        # Extract credentials from environment variables
        username = os.getenv('HOBBYTYME_USERNAME')
        password = os.getenv('HOBBYTYME_PASSWORD')
        
        if not username or not password:
            self.stdout.write(self.style.ERROR('HOBBYTYME_USERNAME and HOBBYTYME_PASSWORD must be set in the .env file'))
            return

        self.stdout.write(f"Authenticating as {username}...")

        import re
        
        session = requests.Session()
        # The base URL that redirects to login and provides the refresh key
        base_url = "https://hobbytyme.com/dealers/index.cfm"
        login_page_url = "https://hobbytyme.com/dealers/index.cfm?action=login&msg=0"
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

                for i, table in enumerate(tables):
                    self.stdout.write(self.style.SUCCESS(f"Table {i}:"))
                    for row in table.find_all('tr'):
                        cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
                        if cols:
                            self.stdout.write('\t'.join(cols))
            else:
                self.stdout.write(self.style.ERROR(f'Failed to fetch backorders: {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {e}"))
