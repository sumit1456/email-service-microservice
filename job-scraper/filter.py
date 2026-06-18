from typing import Dict, Any
import config
import datetime
import re as _re

# Number of days after which a listing is considered stale and filtered out
MAX_LISTING_AGE_DAYS = 30

def _parse_posted_date(date_str: str):
    """
    Tries to parse a posted_date string into a datetime.date object.
    Returns None if the date cannot be parsed (so we don't filter it out).
    Handles formats like:
      - YYYY-MM-DD         (2024-05-10)
      - Mon DD, YYYY       (May 10, 2024)
      - RFC 2822           (Tue, 10 May 2024 00:00:00 +0000)
      - Relative strings   ("3 days ago", "1 month ago") — parsed approximately
    """
    if not date_str or date_str.strip().lower() in ("recently", "unspecified", ""):
        return None

    date_str = date_str.strip()

    # Try ISO format YYYY-MM-DD
    try:
        return datetime.date.fromisoformat(date_str[:10])
    except ValueError:
        pass

    # Try "Month DD, YYYY" e.g. "May 10, 2024"
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    # Try RFC 2822 (email/RSS dates) e.g. "Tue, 10 May 2024 00:00:00 +0000"
    try:
        from email.utils import parsedate
        parsed = parsedate(date_str)
        if parsed:
            return datetime.date(*parsed[:3])
    except Exception:
        pass

    # Try relative dates like "3 days ago", "1 month ago", "2 weeks ago"
    relative = date_str.lower()
    today = datetime.date.today()
    m = _re.search(r'(\d+)\s*(day|week|month|year)', relative)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "day":
            return today - datetime.timedelta(days=n)
        elif unit == "week":
            return today - datetime.timedelta(weeks=n)
        elif unit == "month":
            return today - datetime.timedelta(days=n * 30)
        elif unit == "year":
            return today - datetime.timedelta(days=n * 365)

    return None


def matches_filters(job: Dict[str, Any]) -> bool:
    """
    Applies precise keyword and location filters to a job listing.
    Returns True if the job matches all criteria, False otherwise.
    """
    # 0. Staleness check — filter out listings older than MAX_LISTING_AGE_DAYS
    posted_date_str = job.get("posted_date") or ""
    parsed_date = _parse_posted_date(posted_date_str)
    if parsed_date is not None:
        age_days = (datetime.date.today() - parsed_date).days
        if age_days > MAX_LISTING_AGE_DAYS:
            return False

    # 1. Extract and clean fields
    title = (job.get("title") or "").strip().lower()
    description = (job.get("description") or "").strip().lower()
    location = (job.get("location") or "").strip().lower()
    company = (job.get("company") or "").strip().lower()

    # Combine text for broader searches
    full_text = f"{title} {description}"

    # 2. Check Excluded Keywords (e.g., senior roles)
    for exclude in config.FILTER_EXCLUDE_KEYWORDS:
        # Avoid matching 'lead' inside words like 'plead' by checking word boundaries
        # A simple check: if exclude in full_text
        if exclude in title or f" {exclude} " in f" {description} ":
            # We want to be careful with words like "node.js" or "python"
            # If the title explicitly says "senior", reject
            return False

    # 3. Check Skills (e.g., Java, Spring Boot)
    has_skill = False
    for skill in config.FILTER_KEYWORDS_SKILLS:
        # Match exact skill or boundary checks
        # e.g., 'java' shouldn't match 'javascript' unless it is a word boundary
        if skill == "java":
            # Avoid matching 'javascript' when looking for 'java'
            if "java" in title and "javascript" not in title:
                has_skill = True
                break
            # Check description with word boundaries
            words_desc = description.replace(",", " ").replace(".", " ").split()
            if "java" in words_desc and "javascript" not in description:
                has_skill = True
                break
        else:
            if skill in full_text:
                has_skill = True
                break

    if not has_skill:
        return False

    # 4. Check Roles (e.g., Intern, Trainee)
    has_role = False
    for role in config.FILTER_KEYWORDS_ROLES:
        if role in title or f" {role} " in f" {description} ":
            has_role = True
            break
            
    # Also support titles containing "internship" or description containing "internship"
    if "internship" in title or "internship" in description:
        has_role = True

    if not has_role:
        return False

    # 5. Check Location (e.g., Pune, Remote)
    # If location list is empty, skip location filtering
    if config.FILTER_LOCATIONS:
        has_matching_location = False
        
        # Extended aliases: treat worldwide/global/india/anywhere as remote-friendly
        remote_aliases = ["remote", "work from home", "wfh", "anywhere", "home", "worldwide", "global", "india", "any location", "location independent"]
        is_job_remote = any(x in location for x in remote_aliases)
        
        for loc in config.FILTER_LOCATIONS:
            if loc == "remote" and is_job_remote:
                has_matching_location = True
                break
            elif loc in location:
                has_matching_location = True
                break
                
        # If no matching location found and the location is NOT empty, filter it out
        # (If location is not specified at all, we permit it to avoid missing candidates)
        if location and not has_matching_location:
            return False

    return True
