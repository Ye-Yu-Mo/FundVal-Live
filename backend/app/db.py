import sqlite3
import logging
from .config import Config

logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    """Initialize the database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Funds table - simplistic design, exactly what we need
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS funds (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create an index for searching names, it's cheap and speeds up "LIKE" queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_funds_name ON funds(name);
    """)

    # Positions table - store user holdings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            code TEXT PRIMARY KEY,
            cost REAL NOT NULL DEFAULT 0.0,
            shares REAL NOT NULL DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Subscriptions table - store email alert settings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            email TEXT NOT NULL,
            threshold_up REAL,
            threshold_down REAL,
            enable_digest INTEGER DEFAULT 0,
            digest_time TEXT DEFAULT '14:45',
            enable_volatility INTEGER DEFAULT 1,
            last_notified_at TIMESTAMP,
            last_digest_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, email)
        )
    """)

    # Transactions table - add/reduce position log (T+1 confirm by real NAV)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            op_type TEXT NOT NULL,
            amount_cny REAL,
            shares_redeemed REAL,
            confirm_date TEXT NOT NULL,
            confirm_nav REAL,
            shares_added REAL,
            cost_after REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            applied_at TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_code ON transactions(code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_confirm_date ON transactions(confirm_date);")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized.")
