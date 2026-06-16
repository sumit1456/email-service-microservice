from curl_cffi import requests
from bs4 import BeautifulSoup
import re

IMPERSONATE_BROWSER = "chrome"

def test_site(name, url, check_selector):
    print(f"\nTesting {name} using curl_cffi...")
    try:
        response = requests.get(url, impersonate=IMPERSONATE_BROWSER, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        found_elements = soup.select(check_selector)
        print(f"Found elements matching '{check_selector}': {len(found_elements)}")
        
        is_blocked = response.status_code == 403 or "challenge-platform" in response.text or "cf-challenge" in response.text
        if is_blocked:
            print("STATUS: BLOCKED / Challenged by Cloudflare")
        elif len(found_elements) > 0:
            print("STATUS: SUCCESS (Found jobs on page!)")
        else:
            print("STATUS: UNBLOCKED but no listings found (page structure might be different)")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_site("Internshala", "https://internshala.com/internships/keywords-java/", ".individual_internship, #internship_list_container")
    test_site("Cutshort", "https://cutshort.io/jobs/java-internship", ".job-card, .job-tuple, div[class*='JobCard']")
    test_site("Wellfound", "https://wellfound.com/role/l/java-developer-internship", ".styles_jobCard__S_R_S, .job-listing-container")
