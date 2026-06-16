import sys
import time
import argparse
from db import DeduplicationDB
from scraper import scrape_all
from filter import matches_filters
from notifier import send_notification
import config

def run_job_scraper():
    """Main function to run the scraping and notification pipeline."""
    print("[START] Starting Job Scraper Service pipeline...")
    
    # 1. Initialize Deduplication DB
    try:
        db = DeduplicationDB()
    except Exception as e:
        print(f"[ERROR] Critical Error: Could not initialize database. Aborting. Details: {e}")
        sys.exit(1)
        
    # 1.5. Rate Limit: Check run frequency
    if config.MIN_RUN_INTERVAL_MINUTES > 0:
        current_time = time.time()
        last_run_str = db.get_metadata("last_run")
        if last_run_str:
            try:
                last_run = float(last_run_str)
                elapsed_seconds = current_time - last_run
                min_interval_seconds = config.MIN_RUN_INTERVAL_MINUTES * 60
                
                if elapsed_seconds < min_interval_seconds:
                    remaining_seconds = min_interval_seconds - elapsed_seconds
                    print(f"[INFO] Scraper run skipped. Minimum interval is {config.MIN_RUN_INTERVAL_MINUTES} mins.")
                    print(f"       Last run was {elapsed_seconds / 60:.1f} mins ago. Try again in {remaining_seconds / 60:.1f} mins.")
                    db.close()
                    sys.exit(0)
            except ValueError:
                pass # If last_run is corrupted, ignore and proceed
                
    # 2. Scrape all configured sources
    all_raw_jobs = scrape_all()
    
    # Update last run timestamp in database
    db.set_metadata("last_run", str(time.time()))
    
    print("\n[PROCESS] Processing scraped listings...")
    filtered_jobs_count = 0
    duplicate_jobs_count = 0
    new_jobs = []
    
    # 3. Apply Filters and Deduplicate
    for job in all_raw_jobs:
        # Check filters (skills, roles, locations, exclusions)
        if matches_filters(job):
            url = job.get("url")
            # Deduplicate using DB
            if not db.is_seen(url):
                new_jobs.append(job)
                db.add_seen(url)
            else:
                duplicate_jobs_count += 1
        else:
            filtered_jobs_count += 1

    # 4. Display Stats
    print("\n================== PIPELINE RUN STATS ==================")
    print(f"  Total Raw Listings Scraped:  {len(all_raw_jobs)}")
    print(f"  Filtered Out (Bad Keywords): {filtered_jobs_count}")
    print(f"  Deduplicated (Seen Before):   {duplicate_jobs_count}")
    print(f"  New Matching Listings Found: {len(new_jobs)}")
    print("========================================================\n")
    
    # Print titles of new jobs
    if new_jobs:
        print("New Listings:")
        for idx, job in enumerate(new_jobs, 1):
            print(f"  {idx}. [{job['source']}] {job['title']} at {job['company']} ({job['location']})")
            print(f"     URL: {job['url']}")
    
    # 5. Notify FastAPI Service
    try:
        send_notification(new_jobs, db)
    except Exception as e:
        print(f"[ERROR] Error dispatching notification: {e}")
        
    # 6. Close database
    db.close()
    print("[COMPLETE] Job Scraper Service pipeline complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standalone Job Scraper Service")
    parser.add_argument(
        "--run-once", 
        action="store_true", 
        default=True,
        help="Execute the scraper pipeline once and exit (default behavior)"
    )
    
    args = parser.parse_args()
    run_job_scraper()
