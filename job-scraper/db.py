import sqlite3
import os
from config import get_db_connection_params

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

class DeduplicationDB:
    def __init__(self):
        self.db_params = get_db_connection_params()
        self.use_postgres = False
        self.conn = None
        
        # Try connecting to PostgreSQL if parameters are defined
        if self.db_params:
            if HAS_PSYCOPG2:
                try:
                    # Test connection
                    self.conn = psycopg2.connect(**self.db_params)
                    self.conn.autocommit = True
                    self.use_postgres = True
                    print(f"[OK] Successfully connected to PostgreSQL database: {self.db_params['database']} on {self.db_params['host']}")
                except Exception as e:
                    print(f"[WARN] Failed to connect to PostgreSQL ({e}). Falling back to SQLite.")
                    self.conn = None
            else:
                print("[WARN] DB_URL is configured but 'psycopg2' is not installed. Run 'pip install psycopg2-binary' to enable PostgreSQL database support. Falling back to SQLite.")
                
        # SQLite fallback
        if not self.use_postgres:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_listings.db")
            try:
                self.conn = sqlite3.connect(db_path, check_same_thread=False)
                # SQLite autocommit equivalent or we commit manually
                print(f"[DB] Using SQLite database at: {db_path}")
            except Exception as e:
                print(f"[ERROR] Error initializing SQLite database: {e}")
                raise e

        self.init_table()

    def init_table(self):
        """Creates the tables if they don't already exist."""
        cursor = self.conn.cursor()
        try:
            if self.use_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS seen_listings (
                        id SERIAL PRIMARY KEY,
                        url VARCHAR(2048) UNIQUE NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scraper_metadata (
                        key VARCHAR(255) PRIMARY KEY,
                        value VARCHAR(255) NOT NULL
                    );
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS seen_listings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT UNIQUE NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scraper_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """)
            # For SQLite, commit just in case
            if not self.use_postgres:
                self.conn.commit()
        except Exception as e:
            print(f"[ERROR] Error creating database tables: {e}")
        finally:
            cursor.close()

    def is_seen(self, url: str) -> bool:
        """Checks if a URL has already been processed."""
        if not url:
            return True # Treat empty/invalid URLs as seen to prevent issues
            
        cursor = self.conn.cursor()
        try:
            if self.use_postgres:
                cursor.execute("SELECT 1 FROM seen_listings WHERE url = %s LIMIT 1;", (url,))
            else:
                cursor.execute("SELECT 1 FROM seen_listings WHERE url = ? LIMIT 1;", (url,))
            
            result = cursor.fetchone()
            return result is not None
        except Exception as e:
            print(f"[WARN] Error checking URL in database: {e}")
            return False
        finally:
            cursor.close()

    def add_seen(self, url: str):
        """Marks a URL as seen in the database."""
        if not url:
            return
            
        cursor = self.conn.cursor()
        try:
            if self.use_postgres:
                cursor.execute(
                    "INSERT INTO seen_listings (url) VALUES (%s) ON CONFLICT (url) DO NOTHING;",
                    (url,)
                )
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO seen_listings (url) VALUES (?);",
                    (url,)
                )
                self.conn.commit()
        except Exception as e:
            print(f"[WARN] Error adding URL to database: {e}")
        finally:
            cursor.close()

    def get_metadata(self, key: str) -> str:
        """Retrieves a metadata value by key."""
        cursor = self.conn.cursor()
        try:
            if self.use_postgres:
                cursor.execute("SELECT value FROM scraper_metadata WHERE key = %s LIMIT 1;", (key,))
            else:
                cursor.execute("SELECT value FROM scraper_metadata WHERE key = ? LIMIT 1;", (key,))
            
            result = cursor.fetchone()
            return result[0] if result else ""
        except Exception as e:
            print(f"[WARN] Error fetching metadata key '{key}': {e}")
            return ""
        finally:
            cursor.close()

    def set_metadata(self, key: str, value: str):
        """Sets/updates a metadata value by key."""
        cursor = self.conn.cursor()
        try:
            if self.use_postgres:
                cursor.execute(
                    """
                    INSERT INTO scraper_metadata (key, value) 
                    VALUES (%s, %s) 
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                    """,
                    (key, value)
                )
            else:
                cursor.execute(
                    "INSERT OR REPLACE INTO scraper_metadata (key, value) VALUES (?, ?);",
                    (key, value)
                )
                self.conn.commit()
        except Exception as e:
            print(f"[WARN] Error setting metadata key '{key}': {e}")
        finally:
            cursor.close()

    def close(self):
        """Closes the connection to the database."""
        if self.conn:
            self.conn.close()
            print("[DB] Database connection closed.")
