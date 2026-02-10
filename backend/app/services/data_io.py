import datetime
import logging
from typing import List, Dict, Any, Optional
from ..db import get_db_connection
from ..auth import User, is_multi_user_mode

logger = logging.getLogger(__name__)

# Import order based on dependencies
IMPORT_ORDER = ["settings", "ai_prompts", "accounts", "positions", "transactions", "subscriptions"]

# Sensitive fields that should be masked on export
SENSITIVE_MASK = "***"


def get_user_id_for_query(user: Optional[User]) -> Optional[int]:
    """
    获取用于查询的 user_id

    单用户模式：返回 None
    多用户模式：返回 user.id
    """
    if not is_multi_user_mode():
        return None
    return user.id if user else None


def export_data(modules: List[str], current_user: Optional[User] = None) -> Dict[str, Any]:
    """
    Export selected modules to JSON format.

    Args:
        modules: List of module names to export
        current_user: Current user (for filtering data by user_id)

    Returns:
        Dict containing version, exported_at, metadata, and module data
    """
    if not modules:
        raise ValueError("No modules selected for export")

    user_id = get_user_id_for_query(current_user)

    result = {
        "version": "1.0",
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "metadata": {},
        "modules": {}
    }

    # Export each module
    for module in modules:
        if module == "settings":
            result["modules"]["settings"] = _export_settings(user_id)
            result["metadata"]["total_settings"] = len(result["modules"]["settings"])
        elif module == "ai_prompts":
            result["modules"]["ai_prompts"] = _export_ai_prompts(user_id)
            result["metadata"]["total_ai_prompts"] = len(result["modules"]["ai_prompts"])
        elif module == "accounts":
            result["modules"]["accounts"] = _export_accounts(user_id)
            result["metadata"]["total_accounts"] = len(result["modules"]["accounts"])
        elif module == "positions":
            result["modules"]["positions"] = _export_positions(user_id)
            result["metadata"]["total_positions"] = len(result["modules"]["positions"])
        elif module == "transactions":
            result["modules"]["transactions"] = _export_transactions(user_id)
            result["metadata"]["total_transactions"] = len(result["modules"]["transactions"])
        elif module == "subscriptions":
            result["modules"]["subscriptions"] = _export_subscriptions(user_id)
            result["metadata"]["total_subscriptions"] = len(result["modules"]["subscriptions"])

    return result


def import_data(data: Dict[str, Any], modules: List[str], mode: str, current_user: Optional[User] = None) -> Dict[str, Any]:
    """
    Import selected modules from JSON data.

    Args:
        data: JSON data containing modules
        modules: List of module names to import
        mode: "merge" or "replace"
        current_user: Current user (for setting user_id on imported data)

    Returns:
        Dict containing import results
    """
    if not modules:
        raise ValueError("No modules selected for import")

    if "version" not in data:
        raise ValueError("Missing version field in import data")

    user_id = get_user_id_for_query(current_user)

    # Initialize result
    result = {
        "success": True,
        "total_records": 0,
        "imported": 0,
        "skipped": 0,
        "failed": 0,
        "deleted": 0,
        "details": {}
    }

    conn = get_db_connection()
    # Import modules in dependency order
    ordered_modules = [m for m in IMPORT_ORDER if m in modules]

    for module in ordered_modules:
        if module not in data.get("modules", {}):
            continue

        module_data = data["modules"][module]

        # Skip empty modules
        if not module_data:
            continue

        # Import module
        if module == "settings":
            module_result = _import_settings(conn, module_data, mode, user_id)
        elif module == "ai_prompts":
            module_result = _import_ai_prompts(conn, module_data, mode, user_id)
        elif module == "accounts":
            module_result = _import_accounts(conn, module_data, mode, user_id)
        elif module == "positions":
            module_result = _import_positions(conn, module_data, mode, user_id)
        elif module == "transactions":
            module_result = _import_transactions(conn, module_data, mode, user_id)
        elif module == "subscriptions":
            module_result = _import_subscriptions(conn, module_data, mode, user_id)
        else:
            continue

        # Aggregate results
        result["details"][module] = module_result
        result["total_records"] += module_result.get("total", 0)
        result["imported"] += module_result.get("imported", 0)
        result["skipped"] += module_result.get("skipped", 0)
        result["failed"] += module_result.get("failed", 0)
        result["deleted"] += module_result.get("deleted", 0)

    conn.commit()


    return result


# Export functions

def _export_settings(user_id: Optional[int]) -> Dict[str, str]:
    """
    Export settings (mask sensitive fields)

    单用户模式：导出 settings 表 (user_id IS NULL)
    多用户模式：导出 settings 表 (user_id = ?)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id is None:
        # 单用户模式：从 settings 表读取（user_id IS NULL）
        cursor.execute("SELECT key, value, encrypted FROM settings WHERE user_id IS NULL")
    else:
        # 多用户模式：从 settings 表读取
        cursor.execute(
            "SELECT key, value, encrypted FROM settings WHERE user_id = ?",
            (user_id,)
        )

    settings = {}
    for row in cursor.fetchall():
        key = row["key"]
        value = row["value"]
        encrypted = row["encrypted"]

        # Mask sensitive fields
        if encrypted:
            settings[key] = SENSITIVE_MASK
        else:
            settings[key] = value

    return settings


def _export_ai_prompts(user_id: Optional[int]) -> List[Dict[str, Any]]:
    """
    Export AI prompts (filtered by user_id)

    单用户模式：导出 user_id IS NULL 的 prompts（系统级）
    多用户模式：导出当前用户的 prompts
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id is None:
        # 单用户模式：导出系统级 prompts
        cursor.execute("""
            SELECT name, system_prompt, user_prompt, is_default, created_at, updated_at
            FROM ai_prompts
            WHERE user_id IS NULL
            ORDER BY id
        """)
    else:
        # 多用户模式：导出当前用户的 prompts
        cursor.execute("""
            SELECT name, system_prompt, user_prompt, is_default, created_at, updated_at
            FROM ai_prompts
            WHERE user_id = ?
            ORDER BY id
        """, (user_id,))

    prompts = []
    for row in cursor.fetchall():
        prompts.append({
            "name": row["name"],
            "system_prompt": row["system_prompt"],
            "user_prompt": row["user_prompt"],
            "is_default": bool(row["is_default"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    return prompts



def _export_accounts(user_id: Optional[int]) -> List[Dict[str, Any]]:
    """
    Export accounts (filtered by user_id)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id is None:
        # 单用户模式：导出所有账户
        cursor.execute("""
            SELECT id, name, description, created_at, updated_at
            FROM accounts
            WHERE user_id IS NULL
            ORDER BY id
        """)
    else:
        # 多用户模式：只导出当前用户的账户
        cursor.execute("""
            SELECT id, name, description, created_at, updated_at
            FROM accounts
            WHERE user_id = ?
            ORDER BY id
        """, (user_id,))

    accounts = []
    for row in cursor.fetchall():
        accounts.append({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    return accounts


def _export_positions(user_id: Optional[int]) -> List[Dict[str, Any]]:
    """
    Export positions (filtered by user's accounts)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id is None:
        # 单用户模式：导出所有持仓
        cursor.execute("""
            SELECT p.account_id, p.code, p.cost, p.shares, p.updated_at
            FROM positions p
            JOIN accounts a ON p.account_id = a.id
            WHERE a.user_id IS NULL
            ORDER BY p.account_id, p.code
        """)
    else:
        # 多用户模式：只导出当前用户的持仓
        cursor.execute("""
            SELECT p.account_id, p.code, p.cost, p.shares, p.updated_at
            FROM positions p
            JOIN accounts a ON p.account_id = a.id
            WHERE a.user_id = ?
            ORDER BY p.account_id, p.code
        """, (user_id,))

    positions = []
    for row in cursor.fetchall():
        positions.append({
            "account_id": row["account_id"],
            "code": row["code"],
            "cost": row["cost"],
            "shares": row["shares"],
            "updated_at": row["updated_at"]
        })

    return positions

def _export_transactions(user_id: Optional[int]) -> List[Dict[str, Any]]:
    """
    Export transactions (filtered by user's accounts)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id is None:
        # 单用户模式：导出所有交易记录
        cursor.execute("""
            SELECT t.id, t.account_id, t.code, t.op_type, t.amount_cny, t.shares_redeemed,
                    t.confirm_date, t.confirm_nav, t.shares_added, t.cost_after,
                    t.created_at, t.applied_at
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE a.user_id IS NULL
            ORDER BY t.id
        """)
    else:
        # 多用户模式：只导出当前用户的交易记录
        cursor.execute("""
            SELECT t.id, t.account_id, t.code, t.op_type, t.amount_cny, t.shares_redeemed,
                    t.confirm_date, t.confirm_nav, t.shares_added, t.cost_after,
                    t.created_at, t.applied_at
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE a.user_id = ?
            ORDER BY t.id
        """, (user_id,))

    transactions = []
    for row in cursor.fetchall():
        transactions.append({
            "id": row["id"],
            "account_id": row["account_id"],
            "code": row["code"],
            "op_type": row["op_type"],
            "amount_cny": row["amount_cny"],
            "shares_redeemed": row["shares_redeemed"],
            "confirm_date": row["confirm_date"],
            "confirm_nav": row["confirm_nav"],
            "shares_added": row["shares_added"],
            "cost_after": row["cost_after"],
            "created_at": row["created_at"],
            "applied_at": row["applied_at"]
        })

    return transactions

def _export_subscriptions(user_id: Optional[int]) -> List[Dict[str, Any]]:
    """
    Export subscriptions (filtered by user_id)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id is None:
        # 单用户模式：导出所有订阅
        cursor.execute("""
            SELECT id, code, email, threshold_up, threshold_down,
                    enable_digest, digest_time, enable_volatility,
                    last_notified_at, last_digest_at, created_at
            FROM subscriptions
            WHERE user_id IS NULL
            ORDER BY id
        """)
    else:
        # 多用户模式：只导出当前用户的订阅
        cursor.execute("""
            SELECT id, code, email, threshold_up, threshold_down,
                    enable_digest, digest_time, enable_volatility,
                    last_notified_at, last_digest_at, created_at
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY id
        """, (user_id,))

    subscriptions = []
    for row in cursor.fetchall():
        subscriptions.append({
            "id": row["id"],
            "code": row["code"],
            "email": row["email"],
            "threshold_up": row["threshold_up"],
            "threshold_down": row["threshold_down"],
            "enable_digest": bool(row["enable_digest"]),
            "digest_time": row["digest_time"],
            "enable_volatility": bool(row["enable_volatility"]),
            "last_notified_at": row["last_notified_at"],
            "last_digest_at": row["last_digest_at"],
            "created_at": row["created_at"]
        })

    return subscriptions



# Import functions (to be continued in next chunk)


# Import functions

def _import_settings(conn, data: Dict[str, str], mode: str, user_id: Optional[int]) -> Dict[str, Any]:
    """
    Import settings

    单用户模式：导入到 settings 表 (user_id = NULL)
    多用户模式：导入到 settings 表 (user_id = ?)
    """
    cursor = conn.cursor()
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}

    # Settings always use merge mode
    for key, value in data.items():
        # Skip masked sensitive fields
        if value == SENSITIVE_MASK:
            result["skipped"] += 1
            continue

        try:
            if user_id is None:
                # 单用户模式：导入到 settings 表（user_id = NULL）
                cursor.execute("""
                    INSERT INTO settings (key, value, encrypted, user_id, updated_at)
                    VALUES (?, ?, 0, NULL, CURRENT_TIMESTAMP)
                    ON CONFLICT(key, user_id) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                """, (key, value))
            else:
                # 多用户模式：导入到 settings 表
                cursor.execute("""
                    INSERT INTO settings (key, value, encrypted, user_id, updated_at)
                    VALUES (?, ?, 0, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key, user_id) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                """, (key, value, user_id))

            result["imported"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Failed to import setting {key}: {str(e)}")
            logger.error(f"Failed to import setting {key}: {e}")

    return result


def _import_ai_prompts(conn, data: List[Dict[str, Any]], mode: str, user_id: Optional[int]) -> Dict[str, Any]:
    """
    Import AI prompts (set user_id)
    """
    cursor = conn.cursor()
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}

    # Replace mode: delete user's existing prompts
    if mode == "replace":
        if user_id is None:
            cursor.execute("DELETE FROM ai_prompts WHERE user_id IS NULL")
        else:
            cursor.execute("DELETE FROM ai_prompts WHERE user_id = ?", (user_id,))
        deleted_count = cursor.rowcount
        result["deleted"] = deleted_count

    for prompt in data:
        try:
            name = prompt.get("name")
            if not name:
                result["skipped"] += 1
                result["errors"].append("Missing name field")
                continue

            # Check if prompt with same name exists (merge mode)
            if mode == "merge":
                if user_id is None:
                    cursor.execute("SELECT id FROM ai_prompts WHERE name = ? AND user_id IS NULL", (name,))
                else:
                    cursor.execute("SELECT id FROM ai_prompts WHERE name = ? AND user_id = ?", (name, user_id))

                if cursor.fetchone():
                    result["skipped"] += 1
                    continue

            # Insert with user_id
            cursor.execute("""
                INSERT INTO ai_prompts (name, system_prompt, user_prompt, user_id, is_default)
                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                prompt.get("system_prompt", ""),
                prompt.get("user_prompt", ""),
                user_id,
                1 if prompt.get("is_default") else 0
            ))
            result["imported"] += 1

        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Failed to import prompt {prompt.get('name')}: {str(e)}")
            logger.error(f"Failed to import prompt: {e}")

    return result


def _import_accounts(conn, data: List[Dict[str, Any]], mode: str, user_id: Optional[int]) -> Dict[str, Any]:
    """
    Import accounts (set user_id)
    """
    cursor = conn.cursor()
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}

    # Replace mode: delete user's existing accounts
    if mode == "replace":
        if user_id is None:
            cursor.execute("DELETE FROM accounts WHERE user_id IS NULL")
        else:
            cursor.execute("DELETE FROM accounts WHERE user_id = ?", (user_id,))
        deleted_count = cursor.rowcount
        result["deleted"] = deleted_count

    for account in data:
        try:
            name = account.get("name")
            if not name:
                result["skipped"] += 1
                result["errors"].append("Missing name field")
                continue

            # Check if account with same name exists (merge mode)
            if mode == "merge":
                if user_id is None:
                    cursor.execute("SELECT id FROM accounts WHERE name = ? AND user_id IS NULL", (name,))
                else:
                    cursor.execute("SELECT id FROM accounts WHERE name = ? AND user_id = ?", (name, user_id))

                if cursor.fetchone():
                    result["skipped"] += 1
                    continue

            # Insert with user_id
            cursor.execute("""
                INSERT INTO accounts (name, description, user_id)
                VALUES (?, ?, ?)
            """, (name, account.get("description", ""), user_id))
            result["imported"] += 1

        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Failed to import account {account.get('name')}: {str(e)}")
            logger.error(f"Failed to import account: {e}")

    return result


def _import_positions(conn, data: List[Dict[str, Any]], mode: str, user_id: Optional[int]) -> Dict[str, Any]:
    """
    Import positions (only for user's accounts)
    """
    cursor = conn.cursor()
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}

    # Replace mode: delete positions for user's accounts
    if mode == "replace":
        if user_id is None:
            cursor.execute("""
                DELETE FROM positions
                WHERE account_id IN (SELECT id FROM accounts WHERE user_id IS NULL)
            """)
        else:
            cursor.execute("""
                DELETE FROM positions
                WHERE account_id IN (SELECT id FROM accounts WHERE user_id = ?)
            """, (user_id,))
        deleted_count = cursor.rowcount
        result["deleted"] = deleted_count

    for position in data:
        try:
            account_id = position.get("account_id")
            code = position.get("code")

            if not account_id or not code:
                result["skipped"] += 1
                result["errors"].append("Missing account_id or code field")
                continue

            # Check if account exists and belongs to user
            if user_id is None:
                cursor.execute("SELECT id FROM accounts WHERE id = ? AND user_id IS NULL", (account_id,))
            else:
                cursor.execute("SELECT id FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))

            if not cursor.fetchone():
                result["skipped"] += 1
                result["errors"].append(f"account_id={account_id} does not exist or does not belong to user")
                continue

            # Check if position exists (merge mode)
            if mode == "merge":
                cursor.execute("SELECT 1 FROM positions WHERE account_id = ? AND code = ?", (account_id, code))
                if cursor.fetchone():
                    result["skipped"] += 1
                    continue

            cursor.execute("""
                INSERT INTO positions (account_id, code, cost, shares)
                VALUES (?, ?, ?, ?)
            """, (account_id, code, position.get("cost", 0.0), position.get("shares", 0.0)))
            result["imported"] += 1

        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Failed to import position: {str(e)}")
            logger.error(f"Failed to import position: {e}")

    return result


def _import_transactions(conn, data: List[Dict[str, Any]], mode: str, user_id: Optional[int]) -> Dict[str, Any]:
    """
    Import transactions (only for user's accounts)
    """
    cursor = conn.cursor()
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}

    # Replace mode: delete transactions for user's accounts
    if mode == "replace":
        if user_id is None:
            cursor.execute("""
                DELETE FROM transactions
                WHERE account_id IN (SELECT id FROM accounts WHERE user_id IS NULL)
            """)
        else:
            cursor.execute("""
                DELETE FROM transactions
                WHERE account_id IN (SELECT id FROM accounts WHERE user_id = ?)
            """, (user_id,))
        deleted_count = cursor.rowcount
        result["deleted"] = deleted_count

    for transaction in data:
        try:
            account_id = transaction.get("account_id")
            code = transaction.get("code")

            if not account_id or not code:
                result["skipped"] += 1
                result["errors"].append("Missing account_id or code field")
                continue

            # Check if account exists and belongs to user
            if user_id is None:
                cursor.execute("SELECT id FROM accounts WHERE id = ? AND user_id IS NULL", (account_id,))
            else:
                cursor.execute("SELECT id FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))

            if not cursor.fetchone():
                result["skipped"] += 1
                result["errors"].append(f"account_id={account_id} does not exist or does not belong to user")
                continue

            cursor.execute("""
                INSERT INTO transactions (
                    account_id, code, op_type, amount_cny, shares_redeemed,
                    confirm_date, confirm_nav, shares_added, cost_after, applied_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_id,
                code,
                transaction.get("op_type"),
                transaction.get("amount_cny"),
                transaction.get("shares_redeemed"),
                transaction.get("confirm_date"),
                transaction.get("confirm_nav"),
                transaction.get("shares_added"),
                transaction.get("cost_after"),
                transaction.get("applied_at")
            ))
            result["imported"] += 1

        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Failed to import transaction: {str(e)}")
            logger.error(f"Failed to import transaction: {e}")

    return result


def _import_subscriptions(conn, data: List[Dict[str, Any]], mode: str, user_id: Optional[int]) -> Dict[str, Any]:
    """
    Import subscriptions (set user_id)
    """
    cursor = conn.cursor()
    result = {"total": len(data), "imported": 0, "skipped": 0, "failed": 0, "deleted": 0, "errors": []}

    # Replace mode: delete user's existing subscriptions
    if mode == "replace":
        if user_id is None:
            cursor.execute("DELETE FROM subscriptions WHERE user_id IS NULL")
        else:
            cursor.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        deleted_count = cursor.rowcount
        result["deleted"] = deleted_count

    for subscription in data:
        try:
            code = subscription.get("code")
            email = subscription.get("email")

            if not code or not email:
                result["skipped"] += 1
                result["errors"].append("Missing code or email field")
                continue

            # Check if subscription exists (merge mode)
            if mode == "merge":
                if user_id is None:
                    cursor.execute(
                        "SELECT id FROM subscriptions WHERE code = ? AND email = ? AND user_id IS NULL",
                        (code, email)
                    )
                else:
                    cursor.execute(
                        "SELECT id FROM subscriptions WHERE code = ? AND email = ? AND user_id = ?",
                        (code, email, user_id)
                    )

                if cursor.fetchone():
                    result["skipped"] += 1
                    continue

            # Insert with user_id
            cursor.execute("""
                INSERT INTO subscriptions (
                    code, email, user_id, threshold_up, threshold_down,
                    enable_digest, digest_time, enable_volatility
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                code,
                email,
                user_id,
                subscription.get("threshold_up"),
                subscription.get("threshold_down"),
                1 if subscription.get("enable_digest") else 0,
                subscription.get("digest_time", "14:45"),
                1 if subscription.get("enable_volatility") else 0
            ))
            result["imported"] += 1

        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Failed to import subscription: {str(e)}")
            logger.error(f"Failed to import subscription: {e}")

    return result

