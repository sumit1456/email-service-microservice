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
                "listing_url": link,
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
                                "listing_url": link,
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
                    "listing_url": link,
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
                "listing_url": link or url,
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
                "listing_url": link or url,
                "source": "Cutshort"
            })
        except Exception as e:
            print(f"[WARN] Error parsing Cutshort HTML: {e}")
            continue

    print(f"[OK] Cutshort: Found {len(jobs)} total raw listings")
    return jobs

def _parse_rss_link(item) -> str:
    """
    Robust RSS 2.0 <link> extractor.
    In ElementTree, RSS <link> can have its URL as .text OR as .tail on the
    preceding sibling element. Falls back to <guid> when neither works.
    """
    link = ""
    link_elem = item.find("link")
    if link_elem is not None:
        link = (link_elem.text or "").strip()
        if not link and link_elem.tail:
            link = link_elem.tail.strip()
    # Fallback: <guid isPermaLink="true"> often holds the canonical URL
    if not link or not link.startswith("http"):
        guid_elem = item.find("guid")
        if guid_elem is not None:
            candidate = (guid_elem.text or "").strip()
            if candidate.startswith("http"):
                link = candidate
    return link


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
                title_text = (item.findtext("title") or "").strip()
                link = _parse_rss_link(item)
                description = item.findtext("description") or ""
                pub_date = (item.findtext("pubDate") or "Recently").strip()

                # WWR titles are usually formatted: "Company: Job Title"
                company = "Unknown"
                title = title_text
                if ":" in title_text:
                    parts = title_text.split(":", 1)
                    company = clean_text(parts[0])
                    title = clean_text(parts[1])

                if not title or not link:
                    continue

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
    """
    Scrapes Hacker News 'Ask HN: Who is Hiring?' monthly threads via Algolia.
    - Finds the 2 most-recent 'Who is Hiring' story IDs first.
    - Searches for java/intern comments *within* those threads.
    - Extracts real company apply-URLs from comment <a href> tags.
    - Falls back to the HN thread item link (not raw comment) if no URL found.
    """
    print("[SCRAPE] Scraping Hacker News 'Who is Hiring' threads...")
    jobs = []
    url_pattern = re.compile(r'https?://[^\s<>"\')\]]+')

    # Step 1: Find recent "Ask HN: Who is Hiring?" story IDs via Algolia
    story_ids = []
    try:
        stories_url = (
            "https://hn.algolia.com/api/v1/search_by_date"
            "?query=Ask+HN+Who+is+Hiring&tags=story&hitsPerPage=15"
        )
        resp = std_requests.get(stories_url, headers=DEFAULT_HEADERS, timeout=15)
        if resp.status_code == 200:
            for hit in resp.json().get("hits", []):
                title = (hit.get("title") or "").lower()
                if "who is hiring" in title:
                    story_ids.append(hit.get("objectID", ""))
    except Exception as e:
        print(f"[WARN] Error fetching HN 'Who is Hiring' story IDs: {e}")

    if not story_ids:
        print("[WARN] Could not find 'Who is Hiring' threads. Skipping HN.")
        return jobs

    # Step 2: Search each thread for java/intern comments
    for story_id in story_ids[:2]:          # Limit to 2 most-recent monthly threads
        try:
            comments_url = (
                f"https://hn.algolia.com/api/v1/search"
                f"?query=java+intern&tags=comment,story_{story_id}&hitsPerPage=20"
            )
            response = std_requests.get(comments_url, headers=DEFAULT_HEADERS, timeout=15)
            if response.status_code != 200:
                continue

            for hit in response.json().get("hits", []):
                comment_html = hit.get("comment_text", "")
                author       = hit.get("author", "")
                created_at   = hit.get("created_at_i", 0)
                object_id    = hit.get("objectID", "")

                posted_date = time.strftime('%Y-%m-%d', time.localtime(created_at))

                # --- Extract a real apply URL from the comment ---
                soup_c = BeautifulSoup(comment_html, "html.parser")

                # Priority 1: anchor hrefs inside the comment
                apply_url = ""
                for a in soup_c.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and "ycombinator.com" not in href:
                        apply_url = href.rstrip(".,;)")
                        break

                # Priority 2: bare URLs in the raw HTML text
                if not apply_url:
                    for u in url_pattern.findall(comment_html):
                        if "ycombinator.com" not in u and "algolia.com" not in u:
                            apply_url = u.rstrip(".,;)")
                            break

                # Fallback: link to the monthly thread (not the raw comment)
                if not apply_url:
                    apply_url = f"https://news.ycombinator.com/item?id={story_id}"

                text_clean = soup_c.get_text()
                lines = [l.strip() for l in text_clean.split("\n") if l.strip()]
                first_line = lines[0] if lines else "HN Startup Internship"

                # Many HN hiring posts start with: "Company | Role | Location | ...URL"
                company = f"HN Author: {author}"
                if "|" in first_line:
                    company = clean_text(first_line.split("|")[0])

                # HN listing link = the thread/comment permalink
                hn_listing_url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else f"https://news.ycombinator.com/item?id={story_id}"

                jobs.append({
                    "title": first_line[:100],
                    "company": company,
                    "location": "Remote / Startup",
                    "description": text_clean,
                    "stipend": "Unspecified",
                    "posted_date": posted_date,
                    "url": apply_url,
                    "listing_url": hn_listing_url,
                    "source": "Hacker News"
                })
        except Exception as e:
            print(f"[WARN] Error fetching HN comments for story {story_id}: {e}")

    print(f"[OK] Hacker News: Found {len(jobs)} total raw listings")
    return jobs

# ---------------------------------------------------------------------------
# NEW SCRAPERS  (less-crowded platforms · Pune-local · Remote · Startups)
# ---------------------------------------------------------------------------

def scrape_remoteok() -> list:
    """
    Scrapes Remote OK public JSON API for Java remote jobs.
    No API key required. Endpoint: https://remoteok.com/api?tag=java
    """
    print("[SCRAPE] Scraping Remote OK API...")
    jobs = []
    url = "https://remoteok.com/api?tag=java"
    try:
        response = std_requests.get(
            url,
            headers={**DEFAULT_HEADERS, "Accept": "application/json"},
            timeout=20
        )
        if response.status_code == 200:
            data = response.json()
            for job in data[1:]:            # First element is metadata — skip it
                title      = job.get("position", "")
                company    = job.get("company", "")
                location   = (job.get("location") or "Remote").strip() or "Remote"
                tags       = job.get("tags", [])
                apply_url  = job.get("url", "")
                date_str   = job.get("date", "")
                desc_html  = job.get("description", "")
                description = BeautifulSoup(desc_html, "html.parser").get_text() if desc_html else ""

                if not title or not apply_url:
                    continue

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": f"{description} | Skills: {', '.join(tags)}".strip(" |"),
                    "stipend": "Remote Compensation",
                    "posted_date": date_str[:10] if date_str else "Recently",
                    "url": apply_url,
                    "listing_url": apply_url,
                    "source": "Remote OK"
                })
        else:
            print(f"[WARN] Remote OK API returned {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error reading Remote OK: {e}")

    print(f"[OK] Remote OK: Found {len(jobs)} total raw listings")
    return jobs


def scrape_arbeitnow() -> list:
    """
    Scrapes Arbeitnow public JSON API for remote / startup software jobs.
    No API key required. Endpoint: https://www.arbeitnow.com/api/job-board-api
    """
    print("[SCRAPE] Scraping Arbeitnow API...")
    jobs = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    try:
        response = std_requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200:
            for job in response.json().get("data", []):
                title      = job.get("title", "")
                company    = job.get("company_name", "")
                location   = job.get("location", "Remote")
                is_remote  = job.get("remote", False)
                tags       = job.get("tags", [])
                apply_url  = job.get("url", "")
                created_at = job.get("created_at", "")
                desc_html  = job.get("description", "")
                description = BeautifulSoup(desc_html, "html.parser").get_text() if desc_html else ""

                if not title or not apply_url:
                    continue

                loc_str = "Remote" if is_remote else location

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc_str,
                    "description": f"{description} | Skills: {', '.join(tags)}".strip(" |"),
                    "stipend": "Not Disclosed",
                    "posted_date": str(created_at)[:10] if created_at else "Recently",
                    "url": apply_url,
                    "listing_url": apply_url,
                    "source": "Arbeitnow"
                })
        else:
            print(f"[WARN] Arbeitnow API returned {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error reading Arbeitnow: {e}")

    print(f"[OK] Arbeitnow: Found {len(jobs)} total raw listings")
    return jobs


def scrape_jobicy() -> list:
    """
    Scrapes Jobicy RSS feed for remote Java internships.
    Free public RSS, no key required.
    """
    print("[SCRAPE] Scraping Jobicy RSS...")
    jobs = []
    url = (
        "https://jobicy.com/?feed=job_feed"
        "&search_keywords=java+intern"
        "&job_types=internship"
        "&search_region=anywhere"
    )
    try:
        response = std_requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall(".//item"):
                title_text = (item.findtext("title") or "").strip()
                link       = _parse_rss_link(item)       # reuse the robust helper
                description = item.findtext("description") or ""
                pub_date   = (item.findtext("pubDate") or "Recently").strip()

                # Company from dc:creator element
                creator = item.find("{http://purl.org/dc/elements/1.1/}creator")
                company = creator.text.strip() if (creator is not None and creator.text) else "Remote Company"

                if not title_text or not link:
                    continue

                jobs.append({
                    "title": title_text,
                    "company": company,
                    "location": "Remote",
                    "description": BeautifulSoup(description, "html.parser").get_text(),
                    "stipend": "Not Disclosed",
                    "posted_date": pub_date[:16],
                    "url": link,
                    "listing_url": link,
                    "source": "Jobicy"
                })
        else:
            print(f"[WARN] Jobicy RSS returned {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error reading Jobicy: {e}")

    print(f"[OK] Jobicy: Found {len(jobs)} total raw listings")
    return jobs


def scrape_unstop() -> list:
    """
    Scrapes Unstop (formerly Dare2Compete) for Indian tech internships.
    Uses Unstop's public search API — popular for Pune / India startup roles.
    """
    print("[SCRAPE] Scraping Unstop...")
    jobs = []
    api_url = (
        "https://unstop.com/api/public/opportunity/search-new"
        "?opportunity=internships"
        "&domain=engineering_and_technology"
        "&superType=o"
        "&size=20"
    )
    try:
        response = std_requests.get(
            api_url,
            headers={**DEFAULT_HEADERS, "Accept": "application/json"},
            timeout=20
        )
        if response.status_code == 200:
            result = response.json()
            items = (
                result.get("data", {}).get("data", [])
                or result.get("data", [])
                or result.get("results", [])
            )
            for item in items:
                title = item.get("title") or item.get("name", "")
                if not title:
                    continue

                # Organisation / company
                org     = item.get("organisation") or {}
                company = org.get("name") or item.get("company", "Unknown")

                # Location
                city      = item.get("city", "") or ""
                is_online = item.get("is_online", False)
                location  = "Remote / Online" if is_online else (city or "India")

                # Stipend
                stipend_min = item.get("stipend_min") or 0
                stipend_max = item.get("stipend_max") or 0
                if stipend_min:
                    stipend = f"\u20b9{stipend_min:,}\u2013{stipend_max:,}/mo" if stipend_max else f"\u20b9{stipend_min:,}/mo"
                else:
                    stipend = item.get("stipend") or "Unpaid / Not Disclosed"

                # Canonical URL
                seo_url   = item.get("seo_url", "") or ""
                item_id   = item.get("id", "")
                if seo_url:
                    apply_url = f"https://unstop.com/{seo_url}"
                elif item_id:
                    apply_url = f"https://unstop.com/internships/internship/{item_id}"
                else:
                    apply_url = "https://unstop.com/internships"

                description = item.get("about") or f"Tech internship at {company}"
                deadline    = str(item.get("end_date") or "Recently")[:10]

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": description,
                    "stipend": stipend,
                    "posted_date": deadline,
                    "url": apply_url,
                    "listing_url": apply_url,
                    "source": "Unstop"
                })
        else:
            print(f"[WARN] Unstop API returned {response.status_code}")
    except Exception as e:
        print(f"[WARN] Error reading Unstop: {e}")

    print(f"[OK] Unstop: Found {len(jobs)} total raw listings")
    return jobs


def scrape_indeed_india() -> list:
    """
    Scrapes Indeed India for Java internships in Pune.
    Uses curl_cffi (Chrome TLS impersonation) to bypass bot checks.
    Strips Indeed tracking redirects to return clean job-listing URLs.
    """
    print("[SCRAPE] Scraping Indeed India (Pune)...")
    jobs = []
    url = "https://in.indeed.com/jobs?q=java+internship&l=Pune&sort=date&limit=20"

    html = fetch_html(url)
    if not html:
        return jobs

    soup = BeautifulSoup(html, "lxml")

    containers = (
        soup.select("[data-testid='job-card']") or
        soup.select(".job_seen_beacon") or
        soup.select(".resultContent") or
        soup.select(".tapItem")
    )

    for container in containers:
        try:
            title_elem = (
                container.select_one("h2[class*='jobTitle'] a") or
                container.select_one("a[data-testid='job-title-link']") or
                container.select_one(".jcs-JobTitle") or
                container.select_one("h2 a")
            )
            if not title_elem:
                continue

            title = clean_text(title_elem.text)
            raw_link = title_elem.get("href", "")

            # Build absolute URL and strip tracking redirects → clean /viewjob?jk=... link
            if raw_link and not raw_link.startswith("http"):
                raw_link = f"https://in.indeed.com{raw_link}"
            link = raw_link
            if raw_link and ("clk?" in raw_link or "pagead" in raw_link):
                parsed  = urllib.parse.urlparse(raw_link)
                params  = urllib.parse.parse_qs(parsed.query)
                jk      = params.get("jk", [""])[0]
                if jk:
                    link = f"https://in.indeed.com/viewjob?jk={jk}"

            company_elem = (
                container.select_one("[data-testid='company-name']") or
                container.select_one(".companyName") or
                container.select_one("span[class*='company']")
            )
            company = clean_text(company_elem.text) if company_elem else "Unknown Company"

            loc_elem = (
                container.select_one("[data-testid='job-location']") or
                container.select_one(".companyLocation") or
                container.select_one("div[class*='location']")
            )
            location = clean_text(loc_elem.text) if loc_elem else "Pune, India"

            sal_elem = (
                container.select_one(".salary-snippet-container") or
                container.select_one("[data-testid='attribute_snippet_testid']")
            )
            stipend = clean_text(sal_elem.text) if sal_elem else "Not Disclosed"

            date_elem = (
                container.select_one("[data-testid='myJobsStateDate']") or
                container.select_one(".date")
            )
            posted_date = clean_text(date_elem.text) if date_elem else "Recently"

            if not title or not link:
                continue

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": f"Java internship at {company} — {location}",
                "stipend": stipend,
                "posted_date": posted_date,
                "url": link,
                "listing_url": link,
                "source": "Indeed India"
            })
        except Exception as e:
            print(f"[WARN] Error parsing Indeed India listing: {e}")
            continue

    print(f"[OK] Indeed India: Found {len(jobs)} total raw listings")
    return jobs


def scrape_yc_startups() -> list:
    """
    Scrapes Y Combinator 'Work at a Startup' for engineering internships.
    This is a React SPA — requires ZenRows JS rendering.
    Skipped automatically when ZENROWS_ENABLED=false.
    """
    print("[SCRAPE] Scraping YC Work at a Startup...")
    jobs = []

    if not config.ZENROWS_ENABLED:
        print("[SKIP] YC Work at a Startup is a React SPA — requires ZenRows (ZENROWS_ENABLED=false). Skipping.")
        return jobs

    url = "https://www.workatastartup.com/jobs?role=eng&jobType=intern"
    html = fetch_html(url, use_zenrows=True, js_render=True)
    if not html:
        return jobs

    soup = BeautifulSoup(html, "lxml")

    containers = (
        soup.select(".company-listing") or
        soup.select("div[class*='JobCard']") or
        soup.select(".job-card") or
        soup.select("div[data-company-id]")
    )

    for container in containers:
        try:
            title_elem = (
                container.select_one("a[class*='job-name']") or
                container.select_one(".job-title a") or
                container.select_one("a[href*='/jobs/']") or
                container.select_one("h3 a")
            )
            if not title_elem:
                continue

            title = clean_text(title_elem.text)
            link  = title_elem.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://www.workatastartup.com{link}"

            company_elem = (
                container.select_one("a[class*='company-name']") or
                container.select_one(".company-name") or
                container.select_one("h2 a")
            )
            company = clean_text(company_elem.text) if company_elem else "YC Startup"

            loc_elem = container.select_one(".job-location") or container.select_one("span[class*='location']")
            location = clean_text(loc_elem.text) if loc_elem else "Remote / US"

            comp_elem = container.select_one(".job-compensation") or container.select_one(".compensation")
            stipend   = clean_text(comp_elem.text) if comp_elem else "Startup Equity / Cash"

            if not title or not link:
                continue

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "description": f"YC-backed startup engineering internship at {company}",
                "stipend": stipend,
                "posted_date": "Recently",
                "url": link,
                "listing_url": link,
                "source": "YC Startups"
            })
        except Exception as e:
            print(f"[WARN] Error parsing YC listing: {e}")
            continue

    print(f"[OK] YC Startups: Found {len(jobs)} total raw listings")
    return jobs


# --- MAIN AGGREGATOR ---

def scrape_all() -> list:
    """Runs all scrapers and aggregates the results."""
    all_jobs = []

    scrapers = [
        # ── India / Pune-local ───────────────────────────────
        scrape_internshala,
        scrape_naukri,
        scrape_indeed_india,        # NEW · Pune-local Indeed listings
        scrape_unstop,              # NEW · India startup internships
        # ── Startup-focused ─────────────────────────────────
        scrape_wellfound,
        scrape_cutshort,
        scrape_yc_startups,         # NEW · YC-backed startup internships
        # ── Remote / Global (API/RSS — reliable) ────────────
        scrape_we_work_remotely,
        scrape_remotive,
        scrape_remoteok,            # NEW · Remote OK public API
        scrape_arbeitnow,           # NEW · Arbeitnow public API
        scrape_jobicy,              # NEW · Jobicy RSS feed
        scrape_hacker_news,         # FIXED · Now queries 'Who is Hiring' threads
    ]

    for scraper in scrapers:
        try:
            results = scraper()
            all_jobs.extend(results)
        except Exception as e:
            print(f"[ERROR] Unhandled error running {scraper.__name__}: {e}")

        # Buffer delay between sources to avoid rate-limiting
        time.sleep(config.REQUEST_DELAY)

    print(f"[STATS] Aggregated {len(all_jobs)} total raw job listings.")
    return all_jobs
