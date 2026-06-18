import sys
import os
from db import DeduplicationDB
from filter import matches_filters

def test_filters():
    print("[TEST] Testing Filter Engine...")
    
    test_cases = [
        {
            "job": {
                "title": "Java Developer Intern",
                "company": "Tech Solutions",
                "location": "Pune, India",
                "description": "Looking for a software intern with strong Java skills. Spring Boot is a plus.",
                "stipend": "10,000 /month",
                "url": "https://example.com/job1",
                "posted_date": "Recently"
            },
            "expected": True,
            "reason": "Java + Intern + Pune (Date: Recently)"
        },
        {
            "job": {
                "title": "Java Developer Intern",
                "company": "Tech Solutions",
                "location": "Pune, India",
                "description": "Looking for a software intern with strong Java skills. Spring Boot is a plus.",
                "stipend": "10,000 /month",
                "url": "https://example.com/job_stale",
                "posted_date": "2020-03-24"
            },
            "expected": False,
            "reason": "Filtered out (Date is stale: 2020-03-24)"
        },
        {
            "job": {
                "title": "Java Developer Intern",
                "company": "Tech Solutions",
                "location": "Pune, India",
                "description": "Looking for a software intern with strong Java skills. Spring Boot is a plus.",
                "stipend": "10,000 /month",
                "url": "https://example.com/job_stale_2",
                "posted_date": "31 days ago"
            },
            "expected": False,
            "reason": "Filtered out (Date is stale: 31 days ago)"
        },
        {
            "job": {
                "title": "Java Developer Intern",
                "company": "Tech Solutions",
                "location": "Pune, India",
                "description": "Looking for a software intern with strong Java skills. Spring Boot is a plus.",
                "stipend": "10,000 /month",
                "url": "https://example.com/job_recent_1",
                "posted_date": "2 days ago"
            },
            "expected": True,
            "reason": "Kept (Date is recent: 2 days ago)"
        },
        {
            "job": {
                "title": "Senior Java Developer",
                "company": "Enterprise Corp",
                "location": "Remote",
                "description": "Looking for a Senior Java Developer with 5+ years of experience.",
                "stipend": "1,00,000 /month",
                "url": "https://example.com/job2"
            },
            "expected": False,
            "reason": "Excluded (contains 'Senior' keyword)"
        },
        {
            "job": {
                "title": "React Frontend Intern",
                "company": "Web Studio",
                "location": "Pune",
                "description": "Looking for an intern to work on React.js applications.",
                "stipend": "8,000 /month",
                "url": "https://example.com/job3"
            },
            "expected": False,
            "reason": "Missing skill (no Java keyword)"
        },
        {
            "job": {
                "title": "Java Software Intern",
                "company": "IT Hub",
                "location": "Bangalore",
                "description": "Looking for an intern with Java skills.",
                "stipend": "15,000 /month",
                "url": "https://example.com/job4"
            },
            "expected": False,
            "reason": "Excluded location (Bangalore is not Pune or Remote)"
        },
        {
            "job": {
                "title": "Java Developer Co-op",
                "company": "Remote Startups",
                "location": "Work From Home",
                "description": "We need a Java developer trainee.",
                "stipend": "12,000 /month",
                "url": "https://example.com/job5",
                "posted_date": "1 week ago"
            },
            "expected": True,
            "reason": "Java + Co-op/Trainee + Remote alias (Work From Home) (Date: 1 week ago)"
        }
    ]
    
    passed_all = True
    for idx, tc in enumerate(test_cases, 1):
        result = matches_filters(tc["job"])
        status = "[PASS]" if result == tc["expected"] else "[FAIL]"
        if result != tc["expected"]:
            passed_all = False
        print(f"  [{idx}] {tc['reason']}: {status} (Got: {result}, Expected: {tc['expected']})")
        
    return passed_all

def test_db():
    print("\n[TEST] Testing Database Deduplication (SQLite Fallback)...")
    # Force SQLite for local tests by clearing DB_URL temporarily
    os.environ["DB_URL"] = ""
    
    try:
        db = DeduplicationDB()
        
        # Test URLs
        url1 = "https://test-job-url-1.com"
        url2 = "https://test-job-url-2.com"
        
        # Clear database records if they exist from a previous run
        if os.path.exists("seen_listings.db"):
            cursor = db.conn.cursor()
            cursor.execute("DELETE FROM seen_listings WHERE url LIKE '%test-job-url%';")
            db.conn.commit()
            cursor.close()
            
        print("  - Checking unseen URL...")
        if db.is_seen(url1):
            print("  [FAIL] Unseen URL detected as seen.")
            return False
            
        print("  - Adding URL to database...")
        db.add_seen(url1)
        
        print("  - Checking seen URL...")
        if not db.is_seen(url1):
            print("  [FAIL] Seen URL detected as unseen.")
            return False
            
        print("  - Checking another unseen URL...")
        if db.is_seen(url2):
            print("  [FAIL] Second unseen URL detected as seen.")
            return False
            
        print("  [PASS] Database deduplication test PASSED.")
        db.close()
        
        # Clean up database file
        if os.path.exists("seen_listings.db"):
            try:
                os.remove("seen_listings.db")
                print("  - Cleaned up seen_listings.db file.")
            except Exception as e:
                print(f"  - Warning during cleanup: {e}")
                
        return True
    except Exception as e:
        print(f"  [FAIL] Database error: {e}")
        return False

if __name__ == "__main__":
    print("=== STARTING LOCAL TESTS ===")
    filters_passed = test_filters()
    db_passed = test_db()
    
    print("\n==============================")
    if filters_passed and db_passed:
        print("[PASS] All local tests PASSED!")
        sys.exit(0)
    else:
        print("[FAIL] Some tests FAILED.")
        sys.exit(1)
