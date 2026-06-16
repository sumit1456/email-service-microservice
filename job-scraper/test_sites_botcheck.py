import requests
import sys

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive"
}

NAUKRI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Sec-Ch-Ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

WELLFOUND_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

SITES = [
    {
        "name": "Internshala",
        "url": "https://internshala.com/internships/keywords-java/",
        "headers": DEFAULT_HEADERS
    },
    {
        "name": "Naukri",
        "url": "https://www.naukri.com/java-internship-jobs",
        "headers": NAUKRI_HEADERS
    },
    {
        "name": "Wellfound",
        "url": "https://wellfound.com/role/l/java-developer-internship",
        "headers": WELLFOUND_HEADERS
    },
    {
        "name": "Cutshort",
        "url": "https://cutshort.io/jobs/java-internship",
        "headers": DEFAULT_HEADERS
    },
    {
        "name": "We Work Remotely RSS",
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "headers": DEFAULT_HEADERS
    },
    {
        "name": "Remotive API",
        "url": "https://remotive.com/api/remote-jobs?category=software-development",
        "headers": DEFAULT_HEADERS
    },
    {
        "name": "Hacker News Algolia API",
        "url": "https://hn.algolia.com/api/v1/search?query=java+intern&tags=comment",
        "headers": DEFAULT_HEADERS
    }
]

def test_site(name, url, headers):
    print(f"\nTesting {name} ({url})...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Status Code: {response.status_code}")
        
        # Check if we got Cloudflare/bot protection indicators
        content_len = len(response.text)
        print(f"Response Content Length: {content_len} chars")
        
        if "cloudflare" in response.text.lower() or "captcha" in response.text.lower() or "__cfruid" in response.headers.get("Set-Cookie", ""):
            print("WARNING: Cloudflare or CAPTCHA detected in response!")
        elif response.status_code == 403:
            print("BLOCKED: 403 Forbidden (Likely bot detection)")
        elif response.status_code == 200:
            print("SUCCESS: 200 OK (Content accessible)")
        else:
            print(f"UNKNOWN: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    print("Starting site botcheck tests...")
    for site in SITES:
        test_site(site["name"], site["url"], site["headers"])
