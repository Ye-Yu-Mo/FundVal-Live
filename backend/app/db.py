import sqlite3
import logging
import os
import threading
from pathlib import Path
from contextlib import contextmanager
from .config import Config

logger = logging.getLogger(__name__)

# Thread-local storage for connection pooling
_thread_local = threading.local()

def get_db_connection():
    # Reuse connection within same thread to reduce lock contention
    if hasattr(_thread_local, 'conn') and _thread_local.conn:
        try:
            # Test if connection is still alive
            _thread_local.conn.execute("SELECT 1")
            return _thread_local.conn
        except:
            # Connection is dead, create new one
            _thread_local.conn = None

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


def init_db():
    """Initialize the database schema with migration support."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check database version
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT MAX(version) FROM schema_version")
    current_version = cursor.fetchone()[0] or 0

    logger.info(f"Current database schema version: {current_version}")

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

    # Settings table - store user configuration (for client/desktop)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            encrypted INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 初始化默认配置（如果不存在）
    default_settings = [
        ('OPENAI_API_KEY', '', 1),
        ('OPENAI_API_BASE', 'https://api.openai.com/v1', 0),
        ('AI_MODEL_NAME', 'gpt-3.5-turbo', 0),
        ('SMTP_HOST', 'smtp.gmail.com', 0),
        ('SMTP_PORT', '587', 0),
        ('SMTP_USER', '', 0),
        ('SMTP_PASSWORD', '', 1),
        ('EMAIL_FROM', 'noreply@fundval.live', 0),
        ('INTRADAY_COLLECT_INTERVAL', '5', 0),  # 分时数据采集间隔（分钟）
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO settings (key, value, encrypted) VALUES (?, ?, ?)
    """, default_settings)

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

    # Fund history table - cache historical NAV data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fund_history (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            nav REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (code, date)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fund_history_code ON fund_history(code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fund_history_date ON fund_history(date);")

    # Intraday snapshots table - store intraday valuation data for charts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fund_intraday_snapshots (
            fund_code TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            estimate REAL NOT NULL,
            PRIMARY KEY (fund_code, date, time)
        )
    """)

    # Migration: Drop old incompatible tables
    if current_version < 1:
        logger.info("Running migration: dropping old incompatible tables")
        cursor.execute("DROP TABLE IF EXISTS valuation_accuracy")
        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (1)")

    # Migration: Multi-account support
    if current_version < 2:
        logger.info("Running migration: adding multi-account support")

        # 1. Create accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Insert default account
        cursor.execute("""
            INSERT OR IGNORE INTO accounts (id, name, description)
            VALUES (1, '默认账户', '系统默认账户')
        """)

        # 3. Check if positions table needs migration
        cursor.execute("PRAGMA table_info(positions)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'account_id' not in columns:
            logger.info("Migrating positions table to multi-account")

            # Backup old data
            cursor.execute("SELECT code, cost, shares, updated_at FROM positions")
            old_positions = cursor.fetchall()

            # Drop old table
            cursor.execute("DROP TABLE positions")

            # Create new table with account_id
            cursor.execute("""
                CREATE TABLE positions (
                    account_id INTEGER NOT NULL DEFAULT 1,
                    code TEXT NOT NULL,
                    cost REAL NOT NULL DEFAULT 0.0,
                    shares REAL NOT NULL DEFAULT 0.0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, code),
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE RESTRICT
                )
            """)

            # Restore data with default account_id = 1
            for row in old_positions:
                cursor.execute("""
                    INSERT INTO positions (account_id, code, cost, shares, updated_at)
                    VALUES (1, ?, ?, ?, ?)
                """, row)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_code ON positions(code)")

        # 4. Check if transactions table needs migration
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'account_id' not in columns:
            logger.info("Migrating transactions table to multi-account")

            # Backup old data
            cursor.execute("""
                SELECT id, code, op_type, amount_cny, shares_redeemed,
                       confirm_date, confirm_nav, shares_added, cost_after,
                       created_at, applied_at
                FROM transactions
            """)
            old_transactions = cursor.fetchall()

            # Drop old table
            cursor.execute("DROP TABLE transactions")

            # Create new table with account_id
            cursor.execute("""
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL DEFAULT 1,
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
                    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE RESTRICT
                )
            """)

            # Restore data with default account_id = 1
            for row in old_transactions:
                cursor.execute("""
                    INSERT INTO transactions
                    (id, account_id, code, op_type, amount_cny, shares_redeemed,
                     confirm_date, confirm_nav, shares_added, cost_after,
                     created_at, applied_at)
                    VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, row)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_code ON transactions(code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_confirm_date ON transactions(confirm_date)")

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")

    # Migration: AI Prompts
    if current_version < 3:
        logger.info("Running migration: adding ai_prompts table")

        # Create ai_prompts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                user_prompt TEXT NOT NULL,
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default Linus-style prompt
        cursor.execute("""
            INSERT OR IGNORE INTO ai_prompts (name, system_prompt, user_prompt, is_default)
            VALUES (?, ?, ?, 1)
        """, (
            "Linus 风格（默认）",
            """角色设定
你是 Linus Torvalds，专注于基金的技术面与估值审计。
你极度厌恶情绪化叙事、无关噪音和模棱两可的废话。
你只输出基于数据的逻辑审计结果。

风格要求
- 禁用"首先、其次"、"第一、第二"等解析步骤。
- 句子短，判断极其明确。
- 语气：分析过程冷酷，投资建议务实。
- 核心关注：估值偏差、技术形态、风险收益比。

技术指标合理范围（重要！）
- 夏普比率：0.5-1.0 正常，1.0-1.5 良好，1.5-2.5 优秀，>2.5 异常优秀（罕见但可能）
- 夏普比率计算公式：(年化回报 - 无风险利率) / 年化波动率，其中无风险利率通常为 2-3%
- 最大回撤与年化回报的关系：回撤/回报比 < 0.5 为优秀，0.5-1.0 正常，>1.0 风险较高
- 数据一致性检查：验证夏普比率是否与年化回报、波动率数学一致（允许 ±0.3 误差）

判断逻辑
1. 先验证数据自洽性：夏普比率 ≈ (年化回报 - 2%) / 波动率
2. 如果数据一致，则分析风险收益比是否合理
3. 如果数据不一致，则标记为异常并说明原因""",
            """请对以下基金数据进行逻辑审计，并直接输出审计结果。

【输入数据】
基金代码: {fund_code}
基金名称: {fund_name}
基金类型: {fund_type}
基金经理: {manager}
最新净值: {nav}
实时估值: {estimate} ({est_rate}%)
夏普比率: {sharpe}
年化波动率: {volatility}
最大回撤: {max_drawdown}
年化收益: {annual_return}
持仓集中度: {concentration}%
前10大持仓: {holdings}
历史走势: {history_summary}

【输出要求（严禁分步骤描述分析过程，直接合并为一段精简报告）】
1. 逻辑审计：重点分析技术指标（夏普比率、最大回撤、波动率）、技术位阶（高/低位）及风险特征。
2. 最终结论：一句话总结当前基金的状态（高风险/低风险/正常/异常）。
3. 操作建议：给出 1-2 条冷静、务实的操作指令（持有/止盈/观望/定投）。

请输出纯 JSON 格式（不要用 Markdown 代码块包裹），包含字段:
- summary: 毒舌一句话总结
- risk_level: 风险等级（低风险/中风险/高风险/极高风险）
- analysis_report: 精简综合报告（200字以内）
- suggestions: 操作建议列表（1-3条）"""
        ))

        # Insert a gentle-style prompt as alternative
        cursor.execute("""
            INSERT OR IGNORE INTO ai_prompts (name, system_prompt, user_prompt, is_default)
            VALUES (?, ?, ?, 0)
        """, (
            "温和风格",
            """你是一位专业的基金分析师，擅长用通俗易懂的语言解读基金数据。
你的分析客观、理性，注重风险提示，但语气温和友善。

分析要点：
- 用简单的语言解释技术指标的含义
- 客观评估基金的风险收益特征
- 给出实用的投资建议
- 避免过于激进或保守的判断""",
            """请分析以下基金数据：

【基金信息】
代码: {fund_code}
名称: {fund_name}
类型: {fund_type}
经理: {manager}

【净值数据】
最新净值: {nav}
实时估值: {estimate} ({est_rate}%)

【技术指标】
夏普比率: {sharpe}
年化波动率: {volatility}
最大回撤: {max_drawdown}
年化收益: {annual_return}

【持仓情况】
集中度: {concentration}%
前10大持仓: {holdings}

【历史走势】
{history_summary}

请输出纯 JSON 格式（不要用 Markdown 代码块包裹），包含：
- summary: 一句话总结
- risk_level: 风险等级（低风险/中风险/高风险/极高风险）
- analysis_report: 详细分析报告（300字左右）
- suggestions: 投资建议列表（2-4条）"""
        ))

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")

    # Migration: Add unique constraint to ai_prompts.name
    if current_version < 4:
        logger.info("Running migration: adding unique constraint to ai_prompts.name")

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_prompts_name ON ai_prompts(name)
        """)

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (4)")

    # Migration: Multi-user system tables
    if current_version < 5:
        logger.info("Running migration: adding multi-user system tables")

        # 1. Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create unique index on username
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)
        """)

        # 2. Create user_settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                encrypted INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Create index on user_id
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id)
        """)

        # 3. Add multi_user_mode and allow_registration to settings table
        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value, encrypted)
            VALUES ('multi_user_mode', '0', 0)
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO settings (key, value, encrypted)
            VALUES ('allow_registration', '0', 0)
        """)

        # 4. Add user_id column to accounts table
        cursor.execute("PRAGMA table_info(accounts)")
        accounts_columns = [row[1] for row in cursor.fetchall()]

        if 'user_id' not in accounts_columns:
            logger.info("Adding user_id column to accounts table")
            cursor.execute("""
                ALTER TABLE accounts ADD COLUMN user_id INTEGER
            """)

            # Create index on user_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)
            """)

        # 5. Add user_id column to subscriptions table
        cursor.execute("PRAGMA table_info(subscriptions)")
        subscriptions_columns = [row[1] for row in cursor.fetchall()]

        if 'user_id' not in subscriptions_columns:
            logger.info("Adding user_id column to subscriptions table")
            cursor.execute("""
                ALTER TABLE subscriptions ADD COLUMN user_id INTEGER
            """)

            # Create index on user_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)
            """)

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (5)")

    # Migration: Fix subscriptions UNIQUE constraint for multi-user mode
    if current_version < 6:
        logger.info("Running migration: fixing subscriptions UNIQUE constraint")

        # Backup old data
        cursor.execute("""
            SELECT id, code, email, threshold_up, threshold_down, enable_digest,
                   digest_time, enable_volatility, last_notified_at, last_digest_at,
                   created_at, user_id
            FROM subscriptions
        """)
        old_subscriptions = cursor.fetchall()

        # Drop old table
        cursor.execute("DROP TABLE subscriptions")

        # Create new table with updated UNIQUE constraint
        # UNIQUE(code, email, user_id) allows different users to use same email
        cursor.execute("""
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                email TEXT NOT NULL,
                user_id INTEGER,
                threshold_up REAL,
                threshold_down REAL,
                enable_digest INTEGER DEFAULT 0,
                digest_time TEXT DEFAULT '14:45',
                enable_volatility INTEGER DEFAULT 1,
                last_notified_at TIMESTAMP,
                last_digest_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, email, user_id)
            )
        """)

        # Restore data
        for row in old_subscriptions:
            cursor.execute("""
                INSERT INTO subscriptions
                (id, code, email, user_id, threshold_up, threshold_down, enable_digest,
                 digest_time, enable_volatility, last_notified_at, last_digest_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

        # Recreate index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)
        """)

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (6)")

    # ============================================================================
    # Migration 7: 修改 accounts 表的 UNIQUE 约束
    # 从 UNIQUE(name) 改为 UNIQUE(user_id, name)
    # 允许不同用户创建同名账户
    # ============================================================================
    cursor.execute("SELECT version FROM schema_version WHERE version = 7")
    if not cursor.fetchone():
        logger.info("Running migration 7: Update accounts table UNIQUE constraint")

        # 1. 检查 accounts 表是否有 user_id 列
        cursor.execute("PRAGMA table_info(accounts)")
        columns = {row[1]: row for row in cursor.fetchall()}

        if 'user_id' not in columns:
            logger.error("Migration 7 requires user_id column in accounts table (from migration 5)")
            raise Exception("Please run migration 5 first")

        # 2. 创建新表（带正确的 UNIQUE 约束）
        cursor.execute("""
            CREATE TABLE accounts_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 3. 复制数据
        cursor.execute("""
            INSERT INTO accounts_new (id, name, description, user_id, created_at, updated_at)
            SELECT id, name, description, user_id, created_at, updated_at
            FROM accounts
        """)

        # 4. 删除旧表
        cursor.execute("DROP TABLE accounts")

        # 5. 重命名新表
        cursor.execute("ALTER TABLE accounts_new RENAME TO accounts")

        # 6. 重建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)
        """)

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (7)")
        logger.info("Migration 7 completed: accounts table UNIQUE constraint updated")

    # ============================================================================
    # Migration 8: 为 ai_prompts 表添加 user_id 字段
    # 支持每个用户独立的 AI prompts
    # ============================================================================
    cursor.execute("SELECT version FROM schema_version WHERE version = 8")
    if not cursor.fetchone():
        logger.info("Running migration 8: Add user_id to ai_prompts table")

        # 1. 检查 ai_prompts 表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_prompts'")
        if not cursor.fetchone():
            logger.warning("ai_prompts table does not exist, skipping migration 8")
        else:
            # 2. 检查是否已有 user_id 列
            cursor.execute("PRAGMA table_info(ai_prompts)")
            columns = {row[1]: row for row in cursor.fetchall()}

            if 'user_id' in columns:
                logger.info("user_id column already exists in ai_prompts, skipping migration 8")
            else:
                # 3. 创建新表（带 user_id 字段）
                cursor.execute("""
                    CREATE TABLE ai_prompts_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        system_prompt TEXT NOT NULL,
                        user_prompt TEXT NOT NULL,
                        user_id INTEGER,
                        is_default INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, name),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)

                # 4. 复制数据（现有 prompts 设置为 user_id = NULL，表示系统级/共享）
                cursor.execute("""
                    INSERT INTO ai_prompts_new (id, name, system_prompt, user_prompt, user_id, is_default, created_at, updated_at)
                    SELECT id, name, system_prompt, user_prompt, NULL, is_default, created_at, updated_at
                    FROM ai_prompts
                """)

                # 5. 删除旧表
                cursor.execute("DROP TABLE ai_prompts")

                # 6. 重命名新表
                cursor.execute("ALTER TABLE ai_prompts_new RENAME TO ai_prompts")

                # 7. 重建索引
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ai_prompts_user_id ON ai_prompts(user_id)
                """)

                logger.info("Migration 8 completed: ai_prompts table now has user_id column")

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (8)")

    # Migration 9: Add user_id to settings table for multi-user support
    if current_version < 9:
        logger.info("Running migration 9: Add user_id to settings table")

        # 1. Create new settings table with user_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings_new (
                key TEXT NOT NULL,
                value TEXT,
                encrypted INTEGER DEFAULT 0,
                user_id INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (key, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # 2. Copy existing settings to new table (assign to user_id = NULL for single-user mode)
        cursor.execute("""
            INSERT INTO settings_new (key, value, encrypted, user_id, updated_at)
            SELECT key, value, encrypted, NULL, updated_at
            FROM settings
        """)

        # 3. Drop old table and rename new table
        cursor.execute("DROP TABLE settings")
        cursor.execute("ALTER TABLE settings_new RENAME TO settings")

        # 4. Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_settings_user_id ON settings(user_id)
        """)

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (9)")
        logger.info("Migration 9 completed: settings table now supports multi-user")

    # Migration 10: Merge user_settings into settings and drop user_settings table
    if current_version < 10:
        logger.info("Running migration 10: Merging user_settings into settings")

        # 1. Check if user_settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
        if cursor.fetchone():
            # 2. Migrate data from user_settings to settings
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, encrypted, user_id, updated_at)
                SELECT key, value, encrypted, user_id, updated_at
                FROM user_settings
            """)

            # 3. Drop user_settings table
            cursor.execute("DROP TABLE user_settings")
            logger.info("Migration 10: user_settings table merged and dropped")
        else:
            logger.info("Migration 10: user_settings table does not exist, skipping")

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (10)")
        logger.info("Migration 10 completed: user_settings merged into settings")

    conn.commit()
    conn.close()
    logger.info("Database initialized.")
