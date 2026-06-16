import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
import requests as std_requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
import config

# Standard browser headers (fallback only)
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive"
}

def clean_text(text: str) -> str:
    """Helper to remove excess whitespace from text."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def fetch_with_zenrows(url: str, js_render: bool = True) -> str:
    """Fetches a URL through ZenRows API (uses credits). Only called when ZENROWS_ENABLED=true."""
    if not config.ZENROWS_ENABLED or not config.ZENROWS_API_KEY:
        print(f"[SKIP] ZenRows is disabled or key missing. Skipping {url}")
        return ""
    zenrows_url = "https://api.zenrows.com/v1/"
    params = {
        "apikey": config.ZENROWS_API_KEY,
        "url": url,
        "js_render": "true" if js_render else "false",
    }
    try:
        response = std_requests.get(zenrows_url, params=params, timeout=60)
        if response.status_code == 200:
            print(f"[ZENROWS] Successfully fetched {url}")
            return response.text
        else:
            print(f"[ZENROWS] Failed with code {response.status_code}: {response.text[:200]}")
            return ""
    except Exception as e:
        print(f"[ZENROWS] Error fetching {url}: {e}")
        return ""

def fetch_html(url: str, use_zenrows: bool = False, js_render: bool = False) -> str:
    """
    Tiered fetch strategy:
      1. curl_cffi  — lightweight Chrome TLS impersonation (free, no credits)
      2. ZenRows    — JS-rendering API (costs credits, only if use_zenrows=True AND ZENROWS_ENABLED=True)
      3. std requests fallback — plain requests (last resort)
    """
    # --- Tier 1: curl_cffi (free, impersonates Chrome TLS) ---
    for attempt in range(2):
        try:
            response = cffi_requests.get(url, impersonate="chrome", timeout=15)
            if response.status_code == 200:
                # Check for actual block (not just cloudflare text in footer etc.)
                if "challenge-platform" not in response.text and "cf-challenge" not in response.text:
                    return response.text
                else:
                    print(f"[WARN] curl_cffi got Cloudflare JS challenge on {url}")
                    break  # No point retrying, go to next tier
            elif response.status_code == 403:
                print(f"[WARN] curl_cffi got 403 on {url}. Trying next tier.")
                break
        except Exception as e:
            print(f"[WARN] curl_cffi error on {url} attempt {attempt+1}: {e}")
        time.sleep(config.REQUEST_DELAY)

    # --- Tier 2: ZenRows (only for sites that need JS rendering and when enabled) ---
    if use_zenrows and config.ZENROWS_ENABLED and config.ZENROWS_API_KEY:
        print(f"[INFO] Falling back to ZenRows for {url}")
        html = fetch_with_zenrows(url, js_render=js_render)
        if html:
            return html

    # --- Tier 3: Plain requests fallback ---
    print(f"[WARN] All tiers failed or skipped for {url}. Trying plain requests fallback.")
    for attempt in range(2):
        try:
            response = std_requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"[WARN] Plain requests error on {url} attempt {attempt+1}: {e}")
        time.sleep(config.REQUEST_DELAY)

    return ""

# --- SCRAPER FUNCTIONS ---

def scrape_internshala() -> list:
    """Scrapes Internshala for Java internships."""
    print("[SCRAPE] Scraping Internshala...")
    jobs = []
    # Search for java keyword to capture all relevant internships
    url = "https://internshala.com/internships/keywords-java/"
    html = fetch_html(url)
    if not html:
        return jobs

    soup = BeautifulSoup(html, "lxml")
    # Containers for listings: individual_internship is the standard class name
    containers = soup.select(".individual_internship")
    
    # Fallback to search list container children if class changed
    if not containers:
        containers = soup.select("#internship_list_container .internship_meta")

    for container in containers:
        try:
            # Extract Title and Link
            title_elem = container.select_one(".profile_title_link") or container.select_one(".job-title-container a") or container.select_one(".profile a")
            if not title_elem:
                continue
            
            title = clean_text(title_elem.text)
            link = title_elem.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://internshala.com{link}"

            # Extract Company
            company_elem = container.select_one(".company_and_premium a") or container.select_one(".company-name")
            company = clean_text(company_elem.text) if company_elem else "Unknown Company"

            # Extract Location
            location_elem = container.select_one(".location_link") or container.select_one("#location_names")
            location = clean_text(location_elem.text) if location_elem else "Remote / India"

            # Extract Stipend
            stipend_elem = container.select_one(".stipend") or container.select_one(".stipend_container")
            stipend = clean_text(stipend_elem.text) if stipend_elem else "Unpaid / Not Disclosed"

            # Extract Posted Date
            date_elem = container.select_one(".posted_by_container") or container.select_one(".status-inactive") or container.select_one(".status-active")
            posted_date = clean_text(date_elem.text) if date_elem else "Recently"

            # Try to get short description if present
            desc_elem = container.select_one(".job-description") or container.select_one(".skills_heading")
            description = clean_text(desc_elem.text) if desc_elem else f"Java internship at {company}"

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "stipend": stipend,
                "posted_date": posted_date,
                "url": link,
                "source": "Internshala"
            })
        except Exception as e:
            print(f"[WARN] Error parsing Internshala listing: {e}")
            continue

    print(f"[OK] Internshala: Found {len(jobs)} total raw listings")
    return jobs

def scrape_naukri() -> list:
    """Scrapes Naukri for Java Internships."""
    print("[SCRAPE] Scraping Naukri...")
    jobs = []
    # Using clean search page query parameter
    url = "https://www.naukri.com/java-internship-jobs"
    
    # curl_cffi handles TLS fingerprinting for Naukri — no custom headers needed
    html = fetch_html(url)
    if not html:
        return jobs

    soup = BeautifulSoup(html, "lxml")
    
    # 1. Try parsing JSON INITIAL_STATE script
    parsed_via_json = False
    for script in soup.find_all("script"):
        if script.string and "window.INITIAL_STATE" in script.string:
            try:
                # Find the JSON assignment
                match = re.search(r"window\.INITIAL_STATE\s*=\s*({.*?});", script.string)
                if not match:
                    # Alternative regex check if semicolon is missing
                    match = re.search(r"window\.INITIAL_STATE\s*=\s*({.*})", script.string)
                
                if match:
                    import json
                    json_str = match.group(1)
                    data = json.loads(json_str)
                    
                    # Navigate to jobs array
                    # Usually in data['searchPageMcData']['tuples'] or data['tuples']
                    tuples = (
                        data.get("searchPageMcData", {}).get("tuples", []) or 
                        data.get("tuples", []) or 
                        data.get("jobDetails", [])
                    )
                    
                    for item in tuples:
                        title = item.get("title", "")
                        link = item.get("jdURL", "")
                        if link and not link.startswith("http"):
                            link = f"https://www.naukri.com{link}"
                        
                        company = item.get("companyName", "")
                        
                        # Parse location list
                        loc_placeholders = item.get("placeholders", [])
                        location = "India"
                        stipend = "Not Disclosed"
                        
                        for placeholder in loc_placeholders:
                            p_type = placeholder.get("type", "")
                            if p_type == "location":
                                location = placeholder.get("label", "India")
                            elif p_type == "salary":
                                stipend = placeholder.get("label", "Not Disclosed")
                        
                        posted_date = item.get("footerPlaceholder", {}).get("label", "Recently")
                        description = item.get("jobDescription", f"Java internship at {company}")
                        
                        if title and link:
                            jobs.append({
                                "title": title,
                                "company": company,
                                "location": location,
                                "description": description,
                                "stipend": stipend,
                                "posted_date": posted_date,
                                "url": link,
                                "source": "Naukri"
                            })
                    
                    if jobs:
                        parsed_via_json = True
                        break
            except Exception as e:
                print(f"[WARN] Error parsing Naukri INITIAL_STATE: {e}")
                
    # 2. Fallback: Parse HTML job cards if JSON parse failed
    if not parsed_via_json:
        # Tuples in Naukri usually have class cust-job-tuple or jobTuple
        containers = soup.select(".cust-job-tuple") or soup.select(".jobTuple")
        for container in containers:
            try:
                title_elem = container.select_one("a.title") or container.select_one(".title")
                if not title_elem:
                    continue
                title = clean_text(title_elem.text)
                link = title_elem.get("href", "")
                if link and not link.startswith("http"):
                    link = f"https://www.naukri.com{link}"

                company_elem = container.select_one(".subTitle") or container.select_one(".companyName")
                company = clean_text(company_elem.text) if company_elem else "Unknown Company"

                loc_elem = container.select_one(".location") or container.select_one(".loc")
                location = clean_text(loc_elem.text) if loc_elem else "India"

                sal_elem = container.select_one(".salary")
                stipend = clean_text(sal_elem.text) if sal_elem else "Not Disclosed"

                date_elem = container.select_one(".posted") or container.select_one(".postedVal")
                posted_date = clean_text(date_elem.text) if date_elem else "Recently"

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": f"Java internship at {company}",
                    "stipend": stipend,
                    "posted_date": posted_date,
                    "url": link,
                    "source": "Naukri"
                })
            except Exception as e:
                print(f"[WARN] Error parsing Naukri HTML: {e}")
                continue

    print(f"[OK] Naukri: Found {len(jobs)} total raw listings")
    return jobs

def scrape_wellfound() -> list:
    """Scrapes Wellfound (AngelList) or uses fallback parsing."""
    print("[SCRAPE] Scraping Wellfound (AngelList)...")
    jobs = []
    # Wellfound is heavily protected by Cloudflare JS challenge — requires ZenRows with JS rendering.
    url = "https://wellfound.com/role/l/java-developer-internship"
    
    if not config.ZENROWS_ENABLED:
        print("[SKIP] Wellfound requires ZenRows (ZENROWS_ENABLED=false). Skipping.")
        return jobs
    
    html = fetch_html(url, use_zenrows=True, js_render=True)
    if not html:
        return jobs

    soup = BeautifulSoup(html, "lxml")
    
    # Parse modern Wellfound listing cards (usually inside styled div containers)
    # The structure often has class names like styles_component__xxx or job-card
    containers = soup.select(".styles_jobCard__S_R_S") or soup.select(".job-listing-container") or soup.select(".styles_component__W_Vcf")
    
    # Fallback to general cards if selectors changed
    if not containers:
        containers = soup.select("div[data-testid='JobResultCard']") or soup.select(".styles_resultCard__UaZ_k")

    for container in containers:
        try:
            # Title
            title_elem = container.select_one(".styles_title__J52_s") or container.select_one(".job-title") or container.select_one("a[href*='/jobs/']")
            if not title_elem:
                continue
            title = clean_text(title_elem.text)
            
            link = title_elem.get("href", "") if hasattr(title_elem, "get") else ""
            if link and not link.startswith("http"):
                link = f"https://wellfound.com{link}"

            # Company
            company_elem = container.select_one(".styles_name__A4s_x") or container.select_one(".company-name") or container.select_one(".styles_companyName__UaZ_k")
            company = clean_text(company_elem.text) if company_elem else "Startup"

            # Location
            loc_elem = container.select_one(".styles_location__xxx") or container.select_one(".styles_location__UaZ_k") or container.select_one(".location")
            location = clean_text(loc_elem.text) if loc_elem else "Remote / India"

            # Stipend / Compensation
            comp_elem = container.select_one(".styles_compensation__xxx") or container.select_one(".styles_salary__UaZ_k") or container.select_one(".compensation")
            stipend = clean_text(comp_elem.text) if comp_elem else "Equity / Unspecified"

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": f"Startup software role at {company}",
                "stipend": stipend,
                "posted_date": "Recently",
                "url": link or url,
                "source": "Wellfound"
            })
        except Exception as e:
            print(f"[WARN] Error parsing Wellfound HTML: {e}")
            continue

    print(f"[OK] Wellfound: Found {len(jobs)} total raw listings")
    return jobs

def scrape_cutshort() -> list:
    """Scrapes Cutshort for Java internships."""
    print("[SCRAPE] Scraping Cutshort...")
    jobs = []
    # Cutshort search path
    # Cutshort is a React SPA — needs JS rendering via ZenRows to get listings.
    url = "https://cutshort.io/jobs/java-internship"
    html = fetch_html(url, use_zenrows=True, js_render=True)
    if not html:
        return jobs

    soup = BeautifulSoup(html, "lxml")
    
    # Cutshort listing wrappers usually have card selectors like .job-card or [data-testid='job-card']
    containers = soup.select(".job-card") or soup.select(".job-tuple") or soup.select("div[class*='JobCard']")
    
    for container in containers:
        try:
            # Title
            title_elem = container.select_one("h2") or container.select_one(".job-title") or container.select_one("a[href*='/job/']")
            if not title_elem:
                continue
            title = clean_text(title_elem.text)
            
            link = title_elem.get("href", "") if hasattr(title_elem, "get") else ""
            if link and not link.startswith("http"):
                link = f"https://cutshort.io{link}"

            # Company
            company_elem = container.select_one(".company-name") or container.select_one("span[class*='company']") or container.select_one(".styles_companyName")
            company = clean_text(company_elem.text) if company_elem else "Cutshort Partner"

            # Location
            loc_elem = container.select_one(".location") or container.select_one(".job-location")
            location = clean_text(loc_elem.text) if loc_elem else "India"

            # Stipend
            stipend_elem = container.select_one(".salary") or container.select_one(".compensation")
            stipend = clean_text(stipend_elem.text) if stipend_elem else "Not Disclosed"

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": f"Startup position at {company}",
                "stipend": stipend,
                "posted_date": "Recently",
                "url": link or url,
                "source": "Cutshort"
            })
        except Exception as e:
            print(f"[WARN] Error parsing Cutshort HTML: {e}")
            continue

    print(f"[OK] Cutshort: Found {len(jobs)} total raw listings")
    return jobs

def scrape_we_work_remotely() -> list:
    """Scrapes We Work Remotely RSS programming jobs."""
    print("[SCRAPE] Scraping We Work Remotely...")
    jobs = []
    url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    
    try:
        response = std_requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall(".//item"):
                title_text = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                description = item.find("description").text if item.find("description") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else "Recently"
                
                # WWR titles are usually formatted: "Company: Job Title"
                company = "Unknown"
                title = title_text
                if ":" in title_text:
                    parts = title_text.split(":", 1)
                    company = clean_text(parts[0])
                    title = clean_text(parts[1])
                
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": "Remote",
                    "description": BeautifulSoup(description, "html.parser").get_text() if description else "",
                    "stipend": "Remote Compensation",
                    "posted_date": pub_date,
                    "url": link,
                    "source": "We Work Remotely"
                })
        else:
            print(f"[WARN] WWR RSS returned code {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error reading We Work Remotely RSS: {e}")

    print(f"[OK] We Work Remotely: Found {len(jobs)} total raw listings")
    return jobs

def scrape_remotive() -> list:
    """Scrapes Remotive public JSON API."""
    print("[SCRAPE] Scraping Remotive API...")
    jobs = []
    url = "https://remotive.com/api/remote-jobs?category=software-development"
    
    try:
        response = std_requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            raw_jobs = data.get("jobs", [])
            for job in raw_jobs:
                jobs.append({
                    "title": job.get("title", ""),
                    "company": job.get("company_name", ""),
                    "location": job.get("candidate_required_location", "Remote"),
                    "description": job.get("description", ""),
                    "stipend": job.get("salary", "Not Disclosed"),
                    "posted_date": job.get("publication_date", "Recently"),
                    "url": job.get("url", ""),
                    "source": "Remotive"
                })
        else:
            print(f"[WARN] Remotive API returned code {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error reading Remotive API: {e}")

    print(f"[OK] Remotive: Found {len(jobs)} total raw listings")
    return jobs

def scrape_hacker_news() -> list:
    """Scrapes Hacker News 'Who is Hiring' comments via Algolia API."""
    print("[SCRAPE] Scraping Hacker News Algolia API...")
    jobs = []
    # Search for 'java' and 'intern' in comments
    url = "https://hn.algolia.com/api/v1/search?query=java+intern&tags=comment"
    
    try:
        response = std_requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200:
            hits = response.json().get("hits", [])
            for hit in hits:
                comment_text = hit.get("comment_text", "")
                author = hit.get("author", "")
                created_at = hit.get("created_at_i", 0)
                
                # Convert timestamp
                posted_date = time.strftime('%Y-%m-%d', time.localtime(created_at))
                
                # Link to the specific comment
                object_id = hit.get("objectID", "")
                link = f"https://news.ycombinator.com/item?id={object_id}"
                
                # Clean HTML from comment
                text_clean = BeautifulSoup(comment_text, "html.parser").get_text()
                
                # Parse title/company from first line
                lines = [l.strip() for l in text_clean.split("\n") if l.strip()]
                first_line = lines[0] if lines else "HN Startup Job"
                
                jobs.append({
                    "title": first_line[:100], # Use first line of post as title
                    "company": f"HN Author: {author}",
                    "location": "Remote / Startup",
                    "description": text_clean,
                    "stipend": "Unspecified",
                    "posted_date": posted_date,
                    "url": link,
                    "source": "Hacker News"
                })
        else:
            print(f"[WARN] HN API returned code {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error reading HN API: {e}")

    print(f"[OK] Hacker News: Found {len(jobs)} total raw listings")
    return jobs

# --- MAIN AGGREGATOR ---

def scrape_all() -> list:
    """Runs all scrapers and aggregates the results."""
    all_jobs = []
    
    scrapers = [
        scrape_internshala,
        scrape_naukri,
        scrape_wellfound,
        scrape_cutshort,
        scrape_we_work_remotely,
        scrape_remotive,
        scrape_hacker_news
    ]
    
    for scraper in scrapers:
        try:
            results = scraper()
            all_jobs.extend(results)
        except Exception as e:
            print(f"[ERROR] Unhandled error running {scraper.__name__}: {e}")
            
        # Add buffer sleep between scraping different sources
        time.sleep(config.REQUEST_DELAY)
        
    print(f"[STATS] Aggregated {len(all_jobs)} total raw job listings.")
    return all_jobs
