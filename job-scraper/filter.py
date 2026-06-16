from typing import Dict, Any
import config

def matches_filters(job: Dict[str, Any]) -> bool:
    """
    Applies precise keyword and location filters to a job listing.
    Returns True if the job matches all criteria, False otherwise.
    """
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
        
        # Check aliases for remote
        is_job_remote = any(x in location for x in ["remote", "work from home", "wfh", "anywhere", "home"])
        
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
