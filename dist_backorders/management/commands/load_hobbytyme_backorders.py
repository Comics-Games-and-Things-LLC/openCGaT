import json
import os
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Load backorders from Hobbytyme'

    def handle(self, *args, **options):
        har_path = os.path.expanduser('~/Downloads/hobbytyme.auth.har')
        if not os.path.exists(har_path):
            # Try current directory too in case we are in an environment where ~/Downloads is not accessible
            # or it was copied there.
            har_path = 'hobbytyme.auth.har'
            if not os.path.exists(har_path):
                self.stdout.write(self.style.ERROR(f'HAR file not found at ~/Downloads/hobbytyme.auth.har or current directory'))
                return

        with open(har_path, 'r') as f:
            har_data = json.load(f)

        # Extract credentials from HAR
        credentials = {}
        for entry in har_data['log']['entries']:
            if entry['request']['method'] == 'POST' and 'hobbytyme.com/dealers/index.cfm' in entry['request']['url']:
                post_data = entry['request'].get('postData', {})
                if 'params' in post_data:
                    for param in post_data['params']:
                        credentials[param['name']] = param['value']
                elif 'text' in post_data:
                    from urllib.parse import parse_qs
                    credentials = {k: v[0] for k, v in parse_qs(post_data['text']).items()}
                
                if 'loginUsername' in credentials and 'loginPassword' in credentials:
                    break
        
        if not credentials:
            self.stdout.write(self.style.ERROR('Could not find credentials in HAR file'))
            return

        self.stdout.write(f"Authenticating as {credentials.get('loginUsername')}...")

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
                'loginUsername': credentials.get('loginUsername'),
                'loginPassword': credentials.get('loginPassword'),
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
