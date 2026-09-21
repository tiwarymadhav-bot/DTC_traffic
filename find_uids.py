import requests
import re
from bs4 import BeautifulSoup

def find_uids(route_name):
    # Search for the route
    search_url = f"https://www.dtcbusroutes.in/bus/search/?q={route_name}"
    r = requests.get(search_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Find all links to route pages
    links = [a['href'] for a in soup.find_all('a', href=True) if '/bus/route/' in a['href']]
    print("Links found:", links)
    
    uids = []
    for link in set(links):
        page_url = "https://www.dtcbusroutes.in" + link
        page_r = requests.get(page_url)
        # Look for route_id in the javascript of the page
        match = re.search(r'route_id["\']?\s*:\s*["\']?(\d+)["\']?', page_r.text)
        if match:
            uids.append(match.group(1))
            print(f"Found UID {match.group(1)} for {link}")
    
    return uids

print("534A UIDs:", find_uids("534A"))
print("463 UIDs:", find_uids("463"))
