import os
import urllib.parse
from dotenv import load_dotenv

# Find .env in current directory or parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_env = os.path.join(current_dir, "..", ".env")
local_env = os.path.join(current_dir, ".env")

if os.path.exists(local_env):
    load_dotenv(local_env)
elif os.path.exists(parent_env):
    load_dotenv(parent_env)
else:
    load_dotenv()

# --- DATABASE CONFIGURATION ---
DB_URL = os.getenv("DB_URL")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Helper to parse JDBC PostgreSQL URL to standard PostgreSQL DSN/connection dict
def get_db_connection_params():
    """
    Parses database settings and returns a dict suitable for psycopg2.connect or None.
    If no postgres URL is configured, returns None to fallback to SQLite.
    """
    if not DB_URL:
        return None
    
    url_str = DB_URL
    # Remove jdbc: prefix if present
    if url_str.startswith("jdbc:"):
        url_str = url_str[5:]
    
    try:
        parsed = urllib.parse.urlparse(url_str)
        # Parse query options
        query_params = urllib.parse.parse_qs(parsed.query)
        
        # Determine host and port
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        
        # Path is usually /dbname
        database = parsed.path.lstrip("/") if parsed.path else "postgres"
        
        # Username and password from URL or env overrides
        username = parsed.username or DB_USERNAME or "postgres"
        password = parsed.password or DB_PASSWORD or ""
        
        params = {
            "host": host,
            "port": port,
            "database": database,
            "user": username,
            "password": password,
            "connect_timeout": 5
        }
        
        # Add additional options (e.g. timezone) if present
        if "options" in query_params:
            params["options"] = query_params["options"][0]
            
        return params
    except Exception as e:
        print(f"Error parsing database URL '{DB_URL}': {e}. Falling back to SQLite.")
        return None

# --- FILTER CONFIGURATION ---
# Lists are stored as comma-separated values in environment variables
FILTER_KEYWORDS_SKILLS = [
    k.strip().lower() for k in os.getenv(
        "FILTER_KEYWORDS_SKILLS", "java,spring boot,springboot,jpa,hibernate,spring-boot"
    ).split(",") if k.strip()
]

FILTER_KEYWORDS_ROLES = [
    k.strip().lower() for k in os.getenv(
        "FILTER_KEYWORDS_ROLES", "intern,trainee,co-op,apprentice"
    ).split(",") if k.strip()
]

# We support matching specific locations or remote by default
FILTER_LOCATIONS = [
    k.strip().lower() for k in os.getenv(
        "FILTER_LOCATIONS", "pune,remote"
    ).split(",") if k.strip()
]

FILTER_EXCLUDE_KEYWORDS = [
    k.strip().lower() for k in os.getenv(
        "FILTER_EXCLUDE_KEYWORDS", "senior,lead,staff,principal,manager,node,python,ruby"
    ).split(",") if k.strip()
]

# --- EMAIL & API NOTIFICATION CONFIGURATION ---
EMAIL_SERVICE_PORT = os.getenv("PORT", "8081")
# URL of the email-service API endpoint
EMAIL_SERVICE_URL = os.getenv("EMAIL_SERVICE_URL", f"http://localhost:{EMAIL_SERVICE_PORT}/send-email")

# Email addresses
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "shatekar10@gmail.com")
SENDER_NAME = os.getenv("SENDER_NAME", "Job Scraper Service")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "shatekar10@gmail.com")

# --- RATE LIMIT & SCHEDULING CONFIGURATION ---
# Delay between requests to external sites to avoid rate-limiting/blocks (in seconds)
REQUEST_DELAY = float(os.getenv("SCRAPER_REQUEST_DELAY", "2.0"))

# Minimum time to wait between successive script executions (in minutes)
# Prevents accidental fast looping when run continuously/via cron. Set to 0 to disable.
MIN_RUN_INTERVAL_MINUTES = int(os.getenv("SCRAPER_MIN_RUN_INTERVAL", "60"))

# Maximum number of email digests allowed to be sent per day (e.g. Brevo free tier limit is 300)
MAX_EMAILS_PER_DAY = int(os.getenv("SCRAPER_MAX_EMAILS_PER_DAY", "20"))

# --- ZENROWS CONFIGURATION ---
# Set ZENROWS_ENABLED=true in .env to use ZenRows for JS-heavy / Cloudflare-protected sites
ZENROWS_ENABLED = os.getenv("ZENROWS_ENABLED", "false").lower() == "true"
ZENROWS_API_KEY = os.getenv("ZenROWS_API_KEY", "")
