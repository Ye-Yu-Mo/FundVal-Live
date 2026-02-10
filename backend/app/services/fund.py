import time
import json
import re
import logging
from typing import List, Dict, Any

import pandas as pd
import akshare as ak
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..db import get_db_connection
from ..config import Config

logger = logging.getLogger(__name__)

# Global HTTP session with connection pooling and retry strategy
_http_session = None

def _get_http_session():
    """
    Get or create a global HTTP session with connection pooling.
    This prevents creating new connections for every request.
    """
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)
    return _http_session


def get_fund_type(code: str, name: str) -> str:
    """
    Get fund type from database official_type field.
    Fallback to name-based heuristics if official_type is empty.

    Args:
        code: Fund code
        name: Fund name

    Returns:
        Fund type string
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT type FROM funds WHERE code = ?", (code,))
    row = cursor.fetchone()

    if row and row["type"]:
        return row["type"]


    # Fallback: simple heuristics based on name
    if "债" in name or "纯债" in name or "固收" in name:
        return "债券"
    if "QDII" in name or "纳斯达克" in name or "标普" in name or "恒生" in name:
        return "QDII"
    if "货币" in name:
        return "货币"

    return "未知"


def get_fund_category(fund_type: str) -> str:
    """
    Map official fund type to 4 major categories.

    Args:
        fund_type: Official type from AkShare

    Returns:
        One of: 货币类, 偏债类, 偏股类, 商品类, 未分类
    """
    if not fund_type:
        return "未分类"

    # 货币类
    if fund_type.startswith("货币型") or fund_type == "货币":
        return "货币类"

    # 偏债类
    debt_keywords = [
        "债券型-", "混合型-偏债", "混合型-绝对收益",
        "QDII-纯债", "QDII-混合债", "指数型-固收"
    ]
    if any(fund_type.startswith(k) for k in debt_keywords) or fund_type == "债券":
        return "偏债类"

    # 商品类
    commodity_keywords = ["商品", "QDII-商品", "REITs", "Reits", "QDII-REITs"]
    if any(k in fund_type for k in commodity_keywords):
        return "商品类"

    # 偏股类（最宽泛，放最后）
    equity_keywords = [
        "股票型", "混合型-偏股", "混合型-平衡", "混合型-灵活",
        "指数型-股票", "指数型-海外股票", "指数型-其他",
        "QDII-普通股票", "QDII-混合偏股", "QDII-混合平衡", "QDII-混合灵活",
        "FOF-", "QDII-FOF"
    ]
    if any(fund_type.startswith(k) or k in fund_type for k in equity_keywords):
        return "偏股类"

    # 兜底
    return "未分类"


def get_eastmoney_valuation(code: str) -> Dict[str, Any]:
    """
    Fetch real-time valuation from Tiantian Jijin (Eastmoney) API.
    """
    url = f"http://fundgz.1234567.com.cn/js/{code}.js?rt={int(time.time()*1000)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36)"
    }
    try:
        response = _get_http_session().get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            text = response.text
            # Regex to capture JSON content inside jsonpgz(...)
            # Allow optional semicolon at end
            match = re.search(r"jsonpgz\((.*)\)", text)
            if match and match.group(1):
                data = json.loads(match.group(1))
                return {
                    "name": data.get("name"),
                    "nav": float(data.get("dwjz", 0.0)),
                    "estimate": float(data.get("gsz", 0.0)),
                    "estRate": float(data.get("gszzl", 0.0)),
                    "time": data.get("gztime")
                }
    except Exception as e:
        logger.warning(f"Eastmoney API error for {code}: {e}")
    return {}


def get_sina_valuation(code: str) -> Dict[str, Any]:
    """
    Backup source: Sina Fund API.
    Format: Name, Time, Estimate, NAV, ..., Rate, Date
    """
    url = f"http://hq.sinajs.cn/list=fu_{code}"
    headers = {"Referer": "http://finance.sina.com.cn"}
    try:
        response = _get_http_session().get(url, headers=headers, timeout=5)
        text = response.text
        # var hq_str_fu_005827="Name,15:00:00,1.234,1.230,...";
        match = re.search(r'="(.*)"', text)
        if match and match.group(1):
            parts = match.group(1).split(',')
            if len(parts) >= 8:
                return {
                    # parts[0] is name (GBK), often garbled in utf-8 env, ignore it
                    "estimate": float(parts[2]),
                    "nav": float(parts[3]),
                    "estRate": float(parts[6]),
                    "time": f"{parts[7]} {parts[1]}"
                }
    except Exception as e:
        logger.warning(f"Sina Valuation API error for {code}: {e}")
    return {}


def get_combined_valuation(code: str) -> Dict[str, Any]:
    """
    获取基金估值，优先级：
    1. Eastmoney API
    2. Sina API
    3. 自定义算法估值（基于历史数据）
    4. 兜底：返回昨日净值
    """
    # 1. Try Eastmoney
    data = get_eastmoney_valuation(code)
    if data and data.get("estimate") and data.get("estimate") > 0:
        return data

    # 2. Fallback to Sina
    sina_data = get_sina_valuation(code)
    if sina_data and sina_data.get("estimate") and sina_data.get("estimate") > 0:
        if data:
            data.update(sina_data)
            return data
        return sina_data

    # 3. Try custom estimation algorithm
    from .estimate import estimate_nav
    from datetime import datetime

    try:
        history = get_fund_history(code, limit=30)
        if history and len(history) >= 2:
            ml_result = estimate_nav(code, history)
            if ml_result:
                yesterday_nav = float(history[-1]["nav"])

                # Get fund name from database if not available from API
                fund_name = data.get("name") if data else None
                if not fund_name or fund_name == code:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM funds WHERE code = ?", (code,))
                    row = cursor.fetchone()
                    fund_name = row["name"] if row else code

                return {
                    "code": code,
                    "name": fund_name,
                    "nav": yesterday_nav,
                    "navDate": history[-1]["date"],
                    "estimate": ml_result["estimate"],
                    "estRate": ml_result["est_rate"],
                    "time": datetime.now().strftime("%H:%M"),
                    "source": "ml_estimate",  # 标记来源
                    "confidence": ml_result.get("confidence", 0),
                    "method": ml_result.get("method", "unknown")
                }
    except Exception as e:
        logger.error(f"Custom estimation failed for {code}: {e}")

    # 4. Final fallback: return yesterday's NAV as estimate
    if data:
        return data

    # Last resort: try to get basic info
    try:
        history = get_fund_history(code, limit=1)
        if history:
            # Get fund name from database
            fund_name = code
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM funds WHERE code = ?", (code,))
            row = cursor.fetchone()
            
            if row:
                fund_name = row["name"]

            return {
                "code": code,
                "name": fund_name,
                "nav": float(history[-1]["nav"]),
                "navDate": history[-1]["date"],
                "estimate": float(history[-1]["nav"]),
                "estRate": 0.0,
                "time": "--",
                "source": "fallback"
            }
    except:
        pass

    return {"code": code, "name": code, "nav": 0, "estimate": 0, "estRate": 0}


def search_funds(q: str) -> List[Dict[str, Any]]:
    """
    Search funds by keyword using local SQLite DB.
    Supports both code and name search.
    Results are ordered by relevance: exact code match > code prefix > name match
    """
    if not q:
        return []

    q_clean = q.strip()
    pattern = f"%{q_clean}%"
    prefix_pattern = f"{q_clean}%"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT code, name, type,
            CASE
                WHEN code = ? THEN 1
                WHEN code LIKE ? THEN 2
                WHEN name LIKE ? THEN 3
                ELSE 4
            END as relevance
        FROM funds
        WHERE code LIKE ? OR name LIKE ?
        ORDER BY relevance, code
        LIMIT 30
    """, (q_clean, prefix_pattern, pattern, pattern, pattern))

    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            "id": str(row["code"]),
            "name": row["name"],
            "type": row["type"] or "未知"
        })
    return results


def get_eastmoney_pingzhong_data(code: str) -> Dict[str, Any]:
    """
    Fetch static detailed data from Eastmoney (PingZhongData).
    """
    url = Config.EASTMONEY_DETAILED_API_URL.format(code=code)
    try:
        response = _get_http_session().get(url, timeout=5)
        if response.status_code == 200:
            text = response.text
            data = {}
            name_match = re.search(r'fS_name\s*=\s*"(.*?)";', text)
            if name_match: data["name"] = name_match.group(1)
            
            code_match = re.search(r'fS_code\s*=\s*"(.*?)";', text)
            if code_match: data["code"] = code_match.group(1)
            
            manager_match = re.search(r'Data_currentFundManager\s*=\s*(\[.+?\])\s*;\s*/\*', text)
            if manager_match:
                try:
                    managers = json.loads(manager_match.group(1))
                    if managers:
                        data["manager"] = ", ".join([m["name"] for m in managers])
                except:
                    pass

            # Extract Performance Metrics
            for key in ["syl_1n", "syl_6y", "syl_3y", "syl_1y"]:
                m = re.search(rf'{key}\s*=\s*"(.*?)";', text)
                if m: data[key] = m.group(1)

            # Extract Performance Evaluation (Capability Scores)
            # var Data_performanceEvaluation = {"avr":"72.25","categories":[...],"data":[80.0,70.0...]};
            # Match until `};`
            perf_match = re.search(r'Data_performanceEvaluation\s*=\s*(\{.+?\})\s*;\s*/\*', text)
            if perf_match:
                try:
                    perf = json.loads(perf_match.group(1))
                    if perf and "data" in perf and "categories" in perf:
                        data["performance"] = dict(zip(perf["categories"], perf["data"]))
                except:
                    pass

            # Extract Full History (Data_netWorthTrend)
            # var Data_netWorthTrend = [{"x":1536076800000,"y":1.0,...},...];
            # Relaxed regex: allow various endings (;/* or ; or ;\n)
            history_match = re.search(r'Data_netWorthTrend\s*=\s*(\[.+?\])\s*;', text, re.DOTALL)
            if history_match:
                try:
                    raw_hist = json.loads(history_match.group(1))
                    if not raw_hist:
                        logger.warning(f"Empty Data_netWorthTrend for {code}")
                    else:
                        # Convert to standard format: [{"date": "YYYY-MM-DD", "nav": 1.23}, ...]
                        # x is ms timestamp
                        data["history"] = [
                            {
                                "date": time.strftime('%Y-%m-%d', time.localtime(item['x']/1000)),
                                "nav": float(item['y'])
                            }
                            for item in raw_hist
                            if 'x' in item and 'y' in item  # Validate data structure
                        ]
                except Exception as e:
                    logger.error(f"Failed to parse Data_netWorthTrend for {code}: {e}")
            else:
                # Data_netWorthTrend not found - may be 货币基金 or new page structure
                logger.warning(f"Data_netWorthTrend not found for {code}")

            return data
    except Exception as e:
        logger.warning(f"PingZhong API error for {code}: {e}")
    return {}


def _get_fund_info_from_db(code: str) -> Dict[str, Any]:
    """
    Get fund basic info from local SQLite cache.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, type FROM funds WHERE code = ?", (code,))
        row = cursor.fetchone()
        if row:
            return {"name": row["name"], "type": row["type"]}
    except Exception as e:
        logger.error(f"DB fetch error for {code}: {e}")
    return {}


def _fetch_stock_spots_sina(codes: List[str]) -> Dict[str, float]:
    """
    Fetch real-time stock prices from Sina API in batch.
    Supports A-share (sh/sz), HK (hk), US (gb_).
    """
    if not codes:
        return {}
    
    formatted = []
    # Map cleaned code back to original for result dict
    code_map = {} 
    
    for c in codes:
        if not c: continue
        c_str = str(c).strip()
        prefix = ""
        clean_c = c_str
        
        # Detect Market
        if c_str.isdigit():
            if len(c_str) == 6:
                # A-share
                prefix = "sh" if c_str.startswith(('60', '68', '90', '11')) else "sz"
            elif len(c_str) == 5:
                # HK
                prefix = "hk"
        elif c_str.isalpha():
            # US
            prefix = "gb_"
            clean_c = c_str.lower()
        
        if prefix:
            sina_code = f"{prefix}{clean_c}"
            formatted.append(sina_code)
            code_map[sina_code] = c_str
            
    if not formatted:
        return {}

    url = f"http://hq.sinajs.cn/list={','.join(formatted)}"
    headers = {"Referer": "http://finance.sina.com.cn"}
    
    try:
        response = _get_http_session().get(url, headers=headers, timeout=5)
        results = {}
        for line in response.text.strip().split('\n'):
            if not line or '=' not in line or '"' not in line: continue
            
            # var hq_str_sh600519="..."
            line_key = line.split('=')[0].split('_str_')[-1] # sh600519 or hk00700 or gb_nvda
            original_code = code_map.get(line_key)
            if not original_code: continue

            data_part = line.split('"')[1]
            if not data_part: continue
            parts = data_part.split(',')
            
            change = 0.0
            try:
                if line_key.startswith("gb_"):
                    # US: name, price, change_percent, ...
                    # Example: "英伟达,135.20,2.55,..."
                    if len(parts) > 2:
                        change = float(parts[2])
                elif line_key.startswith("hk"):
                    # HK: en, ch, open, prev_close, high, low, last, ...
                    if len(parts) > 6:
                        prev_close = float(parts[3])
                        last = float(parts[6])
                        if prev_close > 0:
                            change = round((last - prev_close) / prev_close * 100, 2)
                else:
                    # A-share: name, open, prev_close, last, ...
                    if len(parts) > 3:
                        prev_close = float(parts[2])
                        last = float(parts[3])
                        if prev_close > 0:
                            change = round((last - prev_close) / prev_close * 100, 2)
                
                results[original_code] = change
            except:
                continue
                
        return results
    except Exception as e:
        logger.warning(f"Sina fetch failed: {e}")
        return {}


def get_fund_history(code: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Get historical NAV data with database caching.
    If limit >= 9999, fetch all available history.
    """
    from ..db import get_db_connection
    import time

    # 1. Try to get from database cache first
    conn = get_db_connection()
    cursor = conn.cursor()

    # If limit is very large, get all data
    if limit >= 9999:
        cursor.execute("""
            SELECT date, nav, updated_at FROM fund_history
            WHERE code = ?
            ORDER BY date DESC
        """, (code,))
    else:
        cursor.execute("""
            SELECT date, nav, updated_at FROM fund_history
            WHERE code = ?
            ORDER BY date DESC
            LIMIT ?
        """, (code, limit))

    rows = cursor.fetchall()

    # Check if cache is fresh
    cache_valid = False
    if rows:
        latest_update = rows[0]["updated_at"]
        latest_nav_date = rows[0]["date"]
        # Parse timestamp
        try:
            from datetime import datetime
            update_time = datetime.fromisoformat(latest_update)
            age_hours = (datetime.now() - update_time).total_seconds() / 3600

            # Get today's date
            today_str = datetime.now().strftime("%Y-%m-%d")
            current_hour = datetime.now().hour

            # For "all history" requests, require more data to consider cache valid
            min_rows = 10 if limit < 9999 else 100

            # Cache invalidation logic:
            # 1. If it's after 16:00 on a trading day and cache doesn't have today's NAV, invalidate
            # 2. Otherwise, use 24-hour cache
            if current_hour >= 16 and latest_nav_date < today_str:
                # After 16:00, if we don't have today's NAV, force refresh
                cache_valid = False
            else:
                # Normal 24-hour cache
                cache_valid = age_hours < 24 and len(rows) >= min(limit, min_rows)
        except:
            pass

    if cache_valid:
        
        # Reverse to ascending order (oldest to newest) for chart display
        return [{"date": row["date"], "nav": float(row["nav"])} for row in reversed(rows)]

    # 2. Cache miss or stale, fetch from API
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            
            return []

        # If limit < 9999, take only the most recent N records
        if limit < 9999:
            df = df.sort_values(by="净值日期", ascending=False).head(limit)

        # Sort ascending for chart display
        df = df.sort_values(by="净值日期", ascending=True)

        results = []
        for _, row in df.iterrows():
            d = row["净值日期"]
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
            nav_value = float(row["单位净值"])
            results.append({"date": date_str, "nav": nav_value})

            # 3. Save to database cache
            cursor.execute("""
                INSERT OR REPLACE INTO fund_history (code, date, nav, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (code, date_str, nav_value))

        conn.commit()
        
        return results
    except Exception as e:
        logger.error(f"History fetch error for {code}: {e}")
        return []


def get_nav_on_date(code: str, date_str: str) -> float | None:
    """
    Get fund NAV on a specific date (YYYY-MM-DD). Used for T+1 confirm.
    Returns None if that date's NAV is not yet available.
    """
    history = get_fund_history(code, limit=90)
    for item in history:
        if item["date"][:10] == date_str[:10]:
            return item["nav"]
    return None


def _calculate_technical_indicators(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate real technical indicators from NAV history.
    """
    if not history or len(history) < 10:
        return {
            "sharpe": "--",
            "volatility": "--",
            "max_drawdown": "--",
            "annual_return": "--"
        }
    
    try:
        import numpy as np
        # Convert to numpy array of NAVs
        navs = np.array([item['nav'] for item in history])
        
        # 1. Returns (Daily)
        daily_returns = np.diff(navs) / navs[:-1]
        
        # 2. Annualized Return
        total_return = (navs[-1] - navs[0]) / navs[0]
        # Approximate years based on history length
        years = len(history) / 250.0
        annual_return = (1 + total_return)**(1/years) - 1 if years > 0 else 0
        
        # 3. Annualized Volatility
        volatility = np.std(daily_returns) * np.sqrt(250)
        
        # 4. Sharpe Ratio (Risk-free rate = 2%)
        rf = 0.02
        sharpe = (annual_return - rf) / volatility if volatility > 0 else 0
        
        # 5. Max Drawdown
        # Running max
        rolling_max = np.maximum.accumulate(navs)
        drawdowns = (navs - rolling_max) / rolling_max
        max_drawdown = np.min(drawdowns)
        
        return {
            "sharpe": round(float(sharpe), 2),
            "volatility": f"{round(float(volatility) * 100, 2)}%",
            "max_drawdown": f"{round(float(max_drawdown) * 100, 2)}%",
            "annual_return": f"{round(float(annual_return) * 100, 2)}%"
        }
    except Exception as e:
        logger.error(f"Indicator calculation error: {e}")
        return {
            "sharpe": "--",
            "volatility": "--",
            "max_drawdown": "--",
            "annual_return": "--"
        }

def get_fund_intraday(code: str) -> Dict[str, Any]:
    """
    Get fund holdings + real-time valuation estimate.
    """
    # 1) Get real-time valuation (Multi-source)
    em_data = get_combined_valuation(code)
    
    name = em_data.get("name")
    nav = float(em_data.get("nav", 0.0))
    estimate = float(em_data.get("estimate", 0.0))
    est_rate = float(em_data.get("estRate", 0.0))
    update_time = em_data.get("time", time.strftime("%H:%M:%S"))
    source = em_data.get("source")
    method = em_data.get("method")
    confidence = em_data.get("confidence")

    # 1.5) Enrich with detailed info
    pz_data = get_eastmoney_pingzhong_data(code)
    extra_info = {}
    if pz_data.get("name"): extra_info["full_name"] = pz_data["name"]
    if pz_data.get("manager"): extra_info["manager"] = pz_data["manager"]
    for k in ["syl_1n", "syl_6y", "syl_3y", "syl_1y"]:
        if pz_data.get(k): extra_info[k] = pz_data[k]
    
    db_info = _get_fund_info_from_db(code)
    if db_info:
        if not extra_info.get("full_name"): extra_info["full_name"] = db_info["name"]
        extra_info["official_type"] = db_info["type"]

    if not name:
        name = extra_info.get("full_name", f"基金 {code}")
    manager = extra_info.get("manager", "--")

    # 2) Use history from PingZhong for Indicators
    # We take last 250 trading days (approx 1 year)
    history_data = pz_data.get("history", [])
    if history_data:
        # Indicators need 1 year
        tech_indicators = _calculate_technical_indicators(history_data[-250:])
    else:
        # Fallback to AkShare if PingZhong missed it (unlikely)
        history_data = get_fund_history(code, limit=250)
        tech_indicators = _calculate_technical_indicators(history_data)

    # 3) Get holdings from AkShare
    holdings = []
    concentration_rate = 0.0
    try:
        current_year = str(time.localtime().tm_year)
        holdings_df = ak.fund_portfolio_hold_em(symbol=code, date=current_year)
        if holdings_df is None or holdings_df.empty:
             prev_year = str(time.localtime().tm_year - 1)
             holdings_df = ak.fund_portfolio_hold_em(symbol=code, date=prev_year)
             
        if not holdings_df.empty:
            holdings_df = holdings_df.copy()
            if "占净值比例" in holdings_df.columns:
                holdings_df["占净值比例"] = (
                    holdings_df["占净值比例"].astype(str).str.replace("%", "", regex=False)
                )
                holdings_df["占净值比例"] = pd.to_numeric(holdings_df["占净值比例"], errors="coerce").fillna(0.0)
            
            sorted_holdings = holdings_df.sort_values(by="占净值比例", ascending=False)
            top10 = sorted_holdings.head(10)
            concentration_rate = top10["占净值比例"].sum()

            stock_codes = [str(c) for c in holdings_df["股票代码"].tolist() if c]
            spot_map = _fetch_stock_spots_sina(stock_codes)
            
            seen_codes = set()
            for _, row in sorted_holdings.iterrows():
                stock_code = str(row.get("股票代码"))
                percent = float(row.get("占净值比例", 0.0))
                if stock_code in seen_codes or percent < 0.01: continue
                seen_codes.add(stock_code)
                holdings.append({
                    "name": row.get("股票名称"),
                    "percent": percent,
                    "change": spot_map.get(stock_code, 0.0), 
                })
            holdings = holdings[:20]
    except:
        pass

    # 4) Determine sector/type
    sector = get_fund_type(code, name)
    
    response = {
        "id": str(code),
        "name": name,
        "type": sector,
        "manager": manager,
        "nav": nav,
        "estimate": estimate,
        "estRate": est_rate,
        "time": update_time,
        "source": source,
        "method": method,
        "confidence": confidence,
        "holdings": holdings,
        "indicators": {
            "returns": {
                "1M": extra_info.get("syl_1y", "--"),
                "3M": extra_info.get("syl_3y", "--"),
                "6M": extra_info.get("syl_6y", "--"),
                "1Y": extra_info.get("syl_1n", "--")
            },
            "concentration": round(concentration_rate, 2),
            "technical": tech_indicators
        }
    }
    return response