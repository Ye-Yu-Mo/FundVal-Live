import sqlite3
import logging
import os
import threading
from pathlib import Path
from contextlib import contextmanager
from .config import Config

# PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)

# Current database schema version (after rebuild)
CURRENT_SCHEMA_VERSION = 1

# Thread-local storage for connection pooling
_thread_local = threading.local()


def get_db_type() -> str:
    """
    获取当前数据库类型

    Returns:
        str: "sqlite" 或 "postgresql"
    """
    return Config.DB_TYPE


def get_db_connection():
    """
    Get database connection based on DB_TYPE configuration.

    Supports both SQLite and PostgreSQL with thread-local connection pooling.

    Returns:
        Connection object (sqlite3.Connection or psycopg2.connection)
    """
    # Reuse connection within same thread to reduce lock contention
    if hasattr(_thread_local, 'conn') and _thread_local.conn:
        try:
            # Test if connection is still alive
            cursor = _thread_local.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return _thread_local.conn
        except:
            # Connection is dead, create new one
            _thread_local.conn = None

    db_type = get_db_type()

    if db_type == "postgresql":
        # PostgreSQL connection
        if not PSYCOPG2_AVAILABLE:
            raise RuntimeError("psycopg2 is not installed. Run: pip install psycopg2-binary")

        if not Config.DB_URL:
            raise RuntimeError("DATABASE_URL is not configured for PostgreSQL")

        conn = psycopg2.connect(
            Config.DB_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        # PostgreSQL uses autocommit=False by default, which is what we want

    else:
        # SQLite connection
        if not Config.DB_PATH:
            raise RuntimeError("DB_PATH is not configured for SQLite")

        # 确保数据库目录存在
        db_dir = Path(Config.DB_PATH).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row

        # Performance optimizations for concurrent access
        # WAL mode is persistent, only needs to be set once (already enabled)
        # But we set it here to ensure it's enabled even if DB is recreated
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe with WAL
        conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")   # Use memory for temp tables
        conn.execute("PRAGMA busy_timeout=30000")  # 30s timeout for lock contention

    _thread_local.conn = conn
    return conn


@contextmanager
def db_connection():
    """
    Context manager for database transactions with thread-local connection pooling.

    This context manager reuses the thread-local connection and only commits/rollbacks
    transactions, without closing the connection (which would break the pooling).

    Usage:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            # Auto-commits on success, auto-rollbacks on exception
    """
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def check_database_version() -> int:
    """
    Check the current database schema version.

    Returns:
        int: Current schema version (0 if not initialized or schema_version table doesn't exist)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if schema_version table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_version'
        """)
        if not cursor.fetchone():
            return 0

        # Get current version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else 0
    except Exception as e:
        logger.error(f"Error checking database version: {e}")
        return 0


def get_all_tables() -> list[str]:
    """
    Get all table names in the database (excluding SQLite internal tables).

    Returns:
        list[str]: List of table names
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]


def drop_all_tables() -> None:
    """
    Drop all tables in the database (including schema_version).

    WARNING: This will delete all data!
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    tables = get_all_tables()

    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        logger.info(f"Dropped table: {table}")

    conn.commit()
    logger.info(f"Dropped {len(tables)} tables")


def init_db():
    """Initialize the database schema for multi-user mode. Drops all tables if version mismatch."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure schema_version table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    current_version = check_database_version()
    logger.info(f"Current database schema version: {current_version}")

    # If version mismatch, drop all tables and rebuild
    if current_version > 0 and current_version != CURRENT_SCHEMA_VERSION:
        logger.warning(f"Database schema version mismatch (current: {current_version}, expected: {CURRENT_SCHEMA_VERSION}). Dropping all tables and rebuilding...")

        drop_all_tables()

        # Recreate schema_version table
        cursor.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        current_version = 0
        logger.info("All tables dropped. Rebuilding database...")

    # ============================================================================
    # Multi-user tables
    # ============================================================================

    # Users table - store user accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

    # Accounts table - store fund accounts (multi-account support)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)")

    # ============================================================================
    # Fund data tables
    # ============================================================================

    # Funds table - store fund basic info
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS funds (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_funds_name ON funds(name)")

    # Positions table - store user holdings (per account)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            account_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            cost REAL NOT NULL DEFAULT 0.0,
            shares REAL NOT NULL DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (account_id, code),
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_account_id ON positions(account_id)")

    # Transactions table - add/reduce position log (per account)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            op_type TEXT NOT NULL,
            amount_cny REAL,
            shares_redeemed REAL,
            confirm_date TEXT NOT NULL,
            confirm_nav REAL,
            shares_added REAL,
            cost_after REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            applied_at TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_code ON transactions(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_confirm_date ON transactions(confirm_date)")

    # Fund history table - cache historical NAV data (shared across users)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fund_history (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            nav REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (code, date)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fund_history_code ON fund_history(code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fund_history_date ON fund_history(date)")

    # Intraday snapshots table - store intraday valuation data (shared across users)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fund_intraday_snapshots (
            fund_code TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            estimate REAL NOT NULL,
            PRIMARY KEY (fund_code, date, time)
        )
    """)

    # ============================================================================
    # User-specific tables
    # ============================================================================

    # Subscriptions table - store email alert settings (per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            email TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            threshold_up REAL,
            threshold_down REAL,
            enable_digest INTEGER DEFAULT 0,
            digest_time TEXT DEFAULT '14:45',
            enable_volatility INTEGER DEFAULT 1,
            last_notified_at TIMESTAMP,
            last_digest_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, email, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)")

    # Settings table - store configuration (system-level: user_id=NULL, user-level: user_id=<id>)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT NOT NULL,
            value TEXT,
            encrypted INTEGER DEFAULT 0,
            user_id INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (key, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_settings_user_id ON settings(user_id)")

    # Initialize default system settings (user_id = NULL)
    default_settings = [
        ('OPENAI_API_KEY', '', 1, None),
        ('OPENAI_API_BASE', 'https://api.openai.com/v1', 0, None),
        ('AI_MODEL_NAME', 'gpt-3.5-turbo', 0, None),
        ('SMTP_HOST', 'smtp.gmail.com', 0, None),
        ('SMTP_PORT', '587', 0, None),
        ('SMTP_USER', '', 0, None),
        ('SMTP_PASSWORD', '', 1, None),
        ('EMAIL_FROM', 'noreply@fundval.live', 0, None),
        ('INTRADAY_COLLECT_INTERVAL', '5', 0, None),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO settings (key, value, encrypted, user_id) VALUES (?, ?, ?, ?)
    """, default_settings)

    # AI prompts table - store custom AI prompts (per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_prompts_user_id ON ai_prompts(user_id)")

    # AI analysis history table - store AI analysis results (per user)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            fund_code TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            prompt_id INTEGER,
            prompt_name TEXT NOT NULL,
            markdown TEXT NOT NULL,
            indicators_json TEXT,
            status TEXT NOT NULL CHECK(status IN ('success', 'failed')) DEFAULT 'success',
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_history_main
        ON ai_analysis_history(user_id, account_id, fund_code, created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_history_prompt
        ON ai_analysis_history(user_id, prompt_id, created_at DESC)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_analysis_history_user_id
        ON ai_analysis_history(user_id, id)
    """)

    # ============================================================================
    # Set schema version
    # ============================================================================

    if current_version == 0:
        cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (CURRENT_SCHEMA_VERSION,))
        logger.info(f"Database initialized with schema version {CURRENT_SCHEMA_VERSION}")

    conn.commit()
    conn.close()
    logger.info("Database initialized.")
