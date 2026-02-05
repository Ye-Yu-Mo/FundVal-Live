import time
import json
import re
from typing import List, Dict, Any

import pandas as pd
import akshare as ak
import requests

from ..db import get_db_connection
from ..config import Config


# Major Sector Categories Mapping (from MaYiFund)
MAJOR_CATEGORIES = {
    "科技": ["人工智能", "半导体", "云计算", "5G", "光模块", "CPO", "F5G", "通信设备", "PCB", "消费电子",
             "计算机", "软件开发", "信创", "网络安全", "IT服务", "国产软件", "计算机设备", "光通信",
             "算力", "脑机接口", "通信", "电子", "光学光电子", "元件", "存储芯片", "第三代半导体",
             "光刻胶", "电子化学品", "LED", "毫米波", "智能穿戴", "东数西算", "数据要素", "国资云",
             "Web3.0", "AIGC", "AI应用", "AI手机", "AI眼镜", "DeepSeek", "TMT", "科技"],
    "医药健康": ["医药生物", "医疗器械", "生物疫苗", "CRO", "创新药", "精准医疗", "医疗服务", "中药",
                 "化学制药", "生物制品", "基因测序", "超级真菌"],
    "消费": ["食品饮料", "白酒", "家用电器", "纺织服饰", "商贸零售", "新零售", "家居用品", "文娱用品",
             "婴童", "养老产业", "体育", "教育", "在线教育", "社会服务", "轻工制造", "新消费",
             "可选消费", "消费", "家电零部件", "智能家居"],
    "金融": ["银行", "证券", "保险", "非银金融", "国有大型银行", "股份制银行", "城商行", "金融"],
    "能源": ["新能源", "煤炭", "石油石化", "电力", "绿色电力", "氢能源", "储能", "锂电池", "电池",
             "光伏设备", "风电设备", "充电桩", "固态电池", "能源", "煤炭开采", "公用事业", "锂矿"],
    "工业制造": ["机械设备", "汽车", "新能源车", "工程机械", "高端装备", "电力设备", "专用设备",
                 "通用设备", "自动化设备", "机器人", "人形机器人", "汽车零部件", "汽车服务",
                 "汽车热管理", "尾气治理", "特斯拉", "无人驾驶", "智能驾驶", "电网设备", "电机",
                 "高端制造", "工业4.0", "工业互联", "低空经济", "通用航空"],
    "材料": ["有色金属", "黄金", "黄金股", "贵金属", "基础化工", "钢铁", "建筑材料", "稀土永磁", "小金属",
             "工业金属", "材料", "大宗商品", "资源"],
    "军工": ["国防军工", "航天装备", "航空装备", "航海装备", "军工电子", "军民融合", "商业航天",
             "卫星互联网", "航母", "航空机场"],
    "基建地产": ["建筑装饰", "房地产", "房地产开发", "房地产服务", "交通运输", "物流"],
    "环保": ["环保", "环保设备", "环境治理", "垃圾分类", "碳中和", "可控核聚变", "液冷"],
    "传媒": ["传媒", "游戏", "影视", "元宇宙", "超清视频", "数字孪生"],
    "主题": ["国企改革", "一带一路", "中特估", "中字头", "并购重组", "华为", "新兴产业",
             "国家安防", "安全主题", "农牧主题", "农林牧渔", "养殖业", "猪肉", "高端装备"],
    "QDII": ["QDII", "全球", "纳斯达克", "标普", "美国", "德国", "日本", "越南", "印度", "海外", "恒生", "港股", "H股"],
    "债券": ["债", "纯债", "固收", "短债", "中短债", "长债", "国债"]
}


def get_eastmoney_valuation(code: str) -> Dict[str, Any]:
    """
    Fetch real-time valuation from Tiantian Jijin (Eastmoney) API.
    """
    url = f"http://fundgz.1234567.com.cn/js/{code}.js?rt={int(time.time()*1000)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
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
        print(f"Eastmoney API error for {code}: {e}")
    return {}


def get_sina_valuation(code: str) -> Dict[str, Any]:
    """
    Backup source: Sina Fund API.
    Format: Name, Time, Estimate, NAV, ..., Rate, Date
    """
    url = f"http://hq.sinajs.cn/list=fu_{code}"
    headers = {"Referer": "http://finance.sina.com.cn"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
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
        print(f"Sina Valuation API error for {code}: {e}")
    return {}


def get_combined_valuation(code: str) -> Dict[str, Any]:
    """
    Try Eastmoney first, fallback to Sina.
    """
    data = get_eastmoney_valuation(code)
    if not data or data.get("estimate") == 0.0:
        # Fallback to Sina
        sina_data = get_sina_valuation(code)
        if sina_data:
            # Merge Sina info into Eastmoney structure
            data.update(sina_data)
    return data


def search_funds(q: str) -> List[Dict[str, Any]]:
    """
    Search funds by keyword using local SQLite DB.
    """
    if not q:
        return []

    q_clean = q.strip()
    pattern = f"%{q_clean}%"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT code, name, type 
            FROM funds 
            WHERE code LIKE ? OR name LIKE ? 
            LIMIT 20
        """, (pattern, pattern))
        
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "id": str(row["code"]),
                "name": row["name"],
                "type": row["type"] or "未知"
            })
        return results
    finally:
        conn.close()


def get_eastmoney_pingzhong_data(code: str) -> Dict[str, Any]:
    """
    Fetch static detailed data from Eastmoney (PingZhongData).
    """
    url = Config.EASTMONEY_DETAILED_API_URL.format(code=code)
    try:
        response = requests.get(url, timeout=5)
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
            history_match = re.search(r'Data_netWorthTrend\s*=\s*(\[.+?\])\s*;\s*/\*', text)
            if history_match:
                try:
                    raw_hist = json.loads(history_match.group(1))
                    # Convert to standard format: [{"date": "YYYY-MM-DD", "nav": 1.23}, ...]
                    # x is ms timestamp
                    data["history"] = [
                        {
                            "date": time.strftime('%Y-%m-%d', time.localtime(item['x']/1000)),
                            "nav": float(item['y'])
                        }
                        for item in raw_hist
                    ]
                except:
                    pass

            return data
    except Exception as e:
        print(f"PingZhong API error for {code}: {e}")
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
        conn.close()
        if row:
            return {"name": row["name"], "type": row["type"]}
    except Exception as e:
        print(f"DB fetch error for {code}: {e}")
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
        response = requests.get(url, headers=headers, timeout=5)
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
        print(f"Sina fetch failed: {e}")
        return {}


def get_fund_history(code: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Get historical NAV data.
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            return []
        df = df.sort_values(by="净值日期", ascending=False).head(limit)
        df = df.sort_values(by="净值日期", ascending=True)
        results = []
        for _, row in df.iterrows():
            d = row["净值日期"]
            results.append({
                "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10],
                "nav": float(row["单位净值"])
            })
        return results
    except Exception as e:
        print(f"History fetch error for {code}: {e}")
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
        print(f"Indicator calculation error: {e}")
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
    sector = "未知"
    matched_sector = None
    for cat, keywords in MAJOR_CATEGORIES.items():
        if any(kw in name for kw in keywords):
            matched_sector = cat
            break
    
    official_type = extra_info.get("official_type", "")
    if matched_sector:
        sector = matched_sector
    elif official_type:
        sector = official_type
    
    response = {
        "id": str(code),
        "name": name,
        "type": sector, 
        "manager": manager,
        "nav": nav,
        "estimate": estimate,
        "estRate": est_rate,
        "time": update_time,
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