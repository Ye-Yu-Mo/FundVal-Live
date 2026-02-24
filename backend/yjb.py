#!/usr/bin/env python3
"""
养基宝命令行工具
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("错误：缺少 requests 库")
    print("安装：pip install requests")
    sys.exit(1)

# 常量
API_BASE = "http://browser-plug-api.yangjibao.com"
SECRET = "YxmKSrQR4uoJ5lOoWIhcbd7SlUEh9OOc"
TOKEN_FILE = Path.home() / ".yjb_token.json"


# Token 管理
def load_token() -> Optional[str]:
    """从文件加载 token"""
    if not TOKEN_FILE.exists():
        return None
    try:
        with open(TOKEN_FILE, 'r') as f:
            data = json.load(f)
            return data.get('token')
    except Exception as e:
        print(f"警告：读取 token 失败: {e}")
        return None


def save_token(token: str):
    """保存 token 到文件"""
    try:
        with open(TOKEN_FILE, 'w') as f:
            json.dump({
                'token': token,
                'timestamp': int(time.time())
            }, f)
        os.chmod(TOKEN_FILE, 0o600)  # 只有所有者可读写
        print(f"Token 已保存到 {TOKEN_FILE}")
    except Exception as e:
        print(f"错误：保存 token 失败: {e}")


# API 签名
def generate_sign(path: str, token: str, timestamp: int) -> str:
    """生成 API 签名"""
    pathname = ""  # API base 的路径部分，这里是空字符串
    token = token or ""

    # 如果 path 包含查询参数，签名时只用路径部分
    sign_path = path.split('?')[0] if '?' in path else path

    sign_str = pathname + sign_path + token + str(timestamp) + SECRET
    return hashlib.md5(sign_str.encode()).hexdigest()


# HTTP 客户端
class YJBClient:
    """养基宝 API 客户端"""

    def __init__(self, token: Optional[str] = None, debug: bool = False):
        self.token = token or ""
        self.debug = debug
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """发送 API 请求"""
        url = API_BASE + path
        timestamp = int(time.time())
        sign = generate_sign(path, self.token, timestamp)

        headers = {
            'Request-Time': str(timestamp),
            'Request-Sign': sign,
            'Authorization': self.token
        }

        if self.debug:
            print(f"\n[DEBUG] {method} {path}")
            print(f"[DEBUG] Headers: {headers}")

        try:
            resp = self.session.request(method, url, headers=headers, timeout=30, **kwargs)

            if self.debug:
                print(f"[DEBUG] Status: {resp.status_code}")
                print(f"[DEBUG] Response: {resp.text[:200]}")

            if resp.status_code == 429:
                raise Exception("请求频繁，请稍后再试")
            elif resp.status_code == 408:
                raise Exception("请求超时")
            elif resp.status_code == 401:
                raise Exception("未授权，请重新登录")
            elif resp.status_code != 200:
                raise Exception(f"服务请求异常 code: {resp.status_code}")

            data = resp.json()
            if data.get('code') != 200:
                raise Exception(data.get('message', '未知错误'))

            return data.get('data', {})

        except requests.exceptions.RequestException as e:
            raise Exception(f"网络错误: {e}")

    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        """GET 请求"""
        return self.request('GET', path, **kwargs)

    def post(self, path: str, **kwargs) -> Dict[str, Any]:
        """POST 请求"""
        return self.request('POST', path, **kwargs)


# 二维码登录
def qrcode_login(debug: bool = False) -> str:
    """二维码登录"""
    client = YJBClient(debug=debug)

    print("正在获取登录二维码...")
    try:
        qr_data = client.get('/qr_code')
    except Exception as e:
        print(f"错误：获取二维码失败: {e}")
        sys.exit(1)

    qr_id = qr_data.get('id')
    qr_url = qr_data.get('url')

    if not qr_id or not qr_url:
        print("错误：二维码数据格式错误")
        sys.exit(1)

    # 检测依赖
    has_qrcode = False
    has_gui = False

    try:
        import qrcode
        has_qrcode = True
        try:
            from PIL import Image
            import tkinter as tk
            has_gui = True
        except ImportError:
            pass
    except ImportError:
        pass

    # 显示二维码
    root = None

    # 优先在终端显示
    if has_qrcode:
        try:
            import qrcode
            qr = qrcode.QRCode()
            qr.add_data(qr_url)
            qr.make(fit=True)

            print("\n请使用养基宝 APP 扫描二维码登录：\n")
            qr.print_ascii(invert=True)
            print()

        except Exception as e:
            if debug:
                print(f"[DEBUG] 终端显示失败: {e}")
            # 降级到链接
            print(f"\n请访问以下链接查看二维码：")
            print(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_url}")
            print(f"\n或直接扫描此链接：{qr_url}\n")
    else:
        # 没有 qrcode 库，打印链接
        print(f"\n请访问以下链接查看二维码：")
        print(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={qr_url}")
        print(f"\n或直接扫描此链接：{qr_url}\n")

    # 轮询扫码状态
    print("等待扫码...")
    timeout = 120
    interval = 3
    elapsed = 0
    retry_count = 0
    max_retries = 3

    while elapsed < timeout:
        time.sleep(interval)
        elapsed += interval

        try:
            state_data = client.get(f'/qr_code_state/{qr_id}')
            state = state_data.get('state')
            retry_count = 0  # 重置重试计数

            # state: "1" = 等待扫码, 2 = 扫码成功
            if state == 2 or state == '2':
                token = state_data.get('token')
                if token:
                    print("✅ 登录成功！")
                    save_token(token)
                    return token
                else:
                    print("错误：未获取到 token")
                    sys.exit(1)
            elif state == "1":
                # 等待扫码，继续轮询
                pass
            else:
                # 未知状态
                if debug:
                    print(f"[DEBUG] 未知状态: {state}")

        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                print(f"网络错误次数过多: {e}")
                sys.exit(1)
            else:
                print(f"网络异常，正在重试... ({retry_count}/{max_retries})")
                if debug:
                    print(f"[DEBUG] 轮询错误: {e}")

    print("登录超时，请重试")
    sys.exit(1)


# 业务功能
def show_dashboard(client: YJBClient):
    """显示仪表盘"""
    print("=" * 60)
    print("📊 养基宝仪表盘")
    print("=" * 60)

    # 获取指数数据
    try:
        index_data = client.get('/index_data')
        print("\n📈 指数行情:")

        index_map = {
            '1.000001': '上证指数',
            '1.000300': '沪深300',
            '0.399001': '深证成指',
            '0.399006': '创业板指'
        }

        for code, name in index_map.items():
            if code in index_data:
                item = index_data[code]
                price = item.get('v', 'N/A')  # 'v' 是价格字段
                dir_val = item.get('dir', '0')
                try:
                    dir_float = float(dir_val)
                    icon = "🔴" if dir_float > 0 else "🟢" if dir_float < 0 else "⚪"
                    dir_str = f"{dir_float:+.2f}%"
                except:
                    icon = "⚪"
                    dir_str = "N/A"

                print(f"   {icon} {name:8s}  {price:>10s}    {dir_str}")

    except Exception as e:
        print(f"获取指数数据失败: {e}")

    # 获取收益数据
    try:
        account_data = client.get('/account_collect')
        print("\n💰 收益概览:")

        today_income = account_data.get('today_income', 0)
        today_rate = account_data.get('today_income_rate', 0)

        try:
            income_float = float(today_income)
            rate_float = float(today_rate)
            income_icon = "🔴" if income_float > 0 else "🟢" if income_float < 0 else "⚪"

            print(f"   {income_icon} 当日收益: ¥{income_float:.2f}")
            print(f"   {income_icon} 收益率:   {rate_float:+.2f}%")
        except:
            print(f"   当日收益: {today_income}")
            print(f"   收益率:   {today_rate}")

    except Exception as e:
        print(f"获取收益数据失败: {e}")

    print("\n" + "=" * 60)


def search_fund(client: YJBClient, keyword: str):
    """搜索基金"""
    print(f"\n🔍 搜索基金: {keyword}")
    print("-" * 60)

    try:
        funds = client.get(f'/search_fund?keyword={keyword}')

        if not funds:
            print("未找到相关基金")
            return

        for fund in funds:
            code = fund.get('code', 'N/A')
            name = fund.get('name', 'N/A')
            nav = fund.get('nav', 'N/A')
            rate = fund.get('day_growth_rate', 'N/A')

            print(f"{code:8s}  {name:30s}  净值: {nav:>8s}  涨跌: {rate:>8s}")

    except Exception as e:
        print(f"搜索失败: {e}")


def list_accounts(client: YJBClient):
    """列出账户"""
    print("\n📋 账户列表")
    print("-" * 60)

    try:
        # 获取账户列表（基本信息）
        user_data = client.get('/user_account')
        accounts = user_data.get('list', [])

        if not accounts:
            print("暂无账户")
            return

        # 获取账户收益数据
        collect_data = client.get('/account_collect')
        account_data = collect_data.get('account_data', [])

        # 构建 account_id -> 收益数据的映射
        income_map = {acc['account_id']: acc for acc in account_data}

        for acc in accounts:
            acc_id = acc.get('id', 'N/A')
            title = acc.get('title', 'N/A')
            count = acc.get('count', 0)

            # 从收益数据中获取
            income_data = income_map.get(acc_id, {})
            income = income_data.get('today_income', 0)
            rate = income_data.get('today_income_rate', 0)

            try:
                income_float = float(income)
                rate_float = float(rate)
                print(f"ID: {acc_id:<10}  {title:20s}  持仓: {count:2d}  收益: ¥{income_float:>8.2f}  {rate_float:+.2f}%")
            except:
                print(f"ID: {acc_id:<10}  {title:20s}  持仓: {count:2d}  收益: {income}  {rate}")

    except Exception as e:
        print(f"获取账户列表失败: {e}")


def show_holdings(client: YJBClient, account_id: str):
    """显示持仓"""
    print(f"\n💼 账户持仓 (ID: {account_id})")
    print("-" * 100)

    try:
        holdings = client.get(f'/fund_hold?account_id={account_id}')

        if not holdings:
            print("暂无持仓")
            return

        print(f"{'代码':<10s} {'名称':<25s} {'持有份额':<10s} {'当前净值':<10s} {'预估净值':<10s} {'预估涨跌':<10s} {'收益':<10s}")
        print("-" * 100)

        for holding in holdings:
            code = holding.get('code', 'N/A')
            name = holding.get('short_name', 'N/A')
            shares = str(holding.get('hold_share', 'N/A'))
            nav = str(holding.get('last_net', 'N/A'))
            income = str(holding.get('hold_earn', 'N/A'))

            # 预估净值信息（智能选择数据源）
            nv_info = holding.get('nv_info', {})

            # 优先级：gsz（实时估算） > vgsz（预估） > zsgz（昨日估算）
            vgsz = nv_info.get('gsz') or nv_info.get('vgsz') or nv_info.get('zsgz') or 'N/A'
            vgszzl = nv_info.get('gszzl') or nv_info.get('vgszzl') or nv_info.get('zsgzzl') or 'N/A'

            # 格式化预估涨跌幅
            if vgszzl != 'N/A' and vgszzl != '':
                try:
                    vgszzl_float = float(vgszzl)
                    vgszzl = f"{vgszzl_float:+.2f}%"
                except:
                    pass

            print(f"{code:<10s} {name:<25s} {shares:<10s} {nav:<10s} {vgsz:<10s} {vgszzl:<10s} {income:<10s}")

    except Exception as e:
        print(f"获取持仓失败: {e}")


def show_income_chart(client: YJBClient):
    """显示收益曲线"""
    print("\n📈 收益曲线")
    print("-" * 60)

    try:
        data = client.get('/income_line_data?collect=true&date_type=day')
        collect = data.get('collect', {})
        chart_data = collect.get('line_list', [])
        day = collect.get('day', 'N/A')

        if not chart_data:
            print("暂无数据")
            return

        print(f"日期: {day}")
        print(f"\n{'时间':<12s} {'收益率(%)':<12s}")
        print("-" * 60)

        # 只显示每小时的数据（每60条取一条）
        for i, item in enumerate(chart_data):
            if i % 60 == 0 or i == len(chart_data) - 1:
                time_str = item.get('time', 'N/A')
                rate = item.get('rate', 0)
                print(f"{time_str:<12s} {rate:<12}")

    except Exception as e:
        print(f"获取收益曲线失败: {e}")


def show_notice(client: YJBClient):
    """显示公告"""
    print("\n📢 系统公告")
    print("-" * 60)

    try:
        notices = client.get('/notice')

        if not notices:
            print("暂无公告")
            return

        for notice in notices:
            title = notice.get('title', 'N/A')
            content = notice.get('content', 'N/A')
            time_str = notice.get('create_time', 'N/A')

            print(f"\n标题: {title}")
            print(f"时间: {time_str}")
            print(f"内容: {content}")
            print("-" * 60)

    except Exception as e:
        print(f"获取公告失败: {e}")


def show_income_data(client: YJBClient, account_id: Optional[str] = None):
    """显示收益数据"""
    if account_id:
        print(f"\n💰 账户收益数据 (ID: {account_id})")
    else:
        print("\n💰 汇总收益数据")
    print("-" * 60)

    try:
        if account_id:
            data = client.get(f'/income_data?account_id={account_id}')
        else:
            data = client.get('/income_data?collect=true')

        # API 返回的是数字，不是字典
        if isinstance(data, (int, float)):
            print(f"累计收益: ¥{data:.2f}")
        else:
            # 如果是字典，尝试提取字段
            today_income = data.get('today_income', 'N/A')
            today_rate = data.get('today_income_rate', 'N/A')
            total_income = data.get('total_income', 'N/A')
            total_rate = data.get('total_income_rate', 'N/A')

            print(f"当日收益:   {today_income}")
            print(f"当日收益率: {today_rate}")
            print(f"累计收益:   {total_income}")
            print(f"累计收益率: {total_rate}")

    except Exception as e:
        print(f"获取收益数据失败: {e}")


# 命令行入口
def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='养基宝命令行工具')
    parser.add_argument('--login', action='store_true', help='重新登录')
    parser.add_argument('--search', type=str, metavar='KEYWORD', help='搜索基金')
    parser.add_argument('--accounts', action='store_true', help='列出所有账户')
    parser.add_argument('--holdings', type=str, metavar='ID', help='查看账户持仓')
    parser.add_argument('--income-chart', action='store_true', help='查看收益曲线')
    parser.add_argument('--income-data', type=str, nargs='?', const='', metavar='ID', help='查看收益数据（不指定ID则查看汇总）')
    parser.add_argument('--notice', action='store_true', help='查看系统公告')
    parser.add_argument('--debug', action='store_true', help='显示详细调试信息')

    args = parser.parse_args()

    # 登录
    if args.login:
        qrcode_login(debug=args.debug)
        return

    # 检查 token
    token = load_token()
    if not token:
        print("未登录，请先运行：python3 yjb_tool.py --login")
        sys.exit(1)

    # 创建客户端
    client = YJBClient(token=token, debug=args.debug)

    # 执行功能
    try:
        if args.search:
            search_fund(client, args.search)
        elif args.accounts:
            list_accounts(client)
        elif args.holdings:
            show_holdings(client, args.holdings)
        elif args.income_chart:
            show_income_chart(client)
        elif args.income_data is not None:
            show_income_data(client, args.income_data if args.income_data else None)
        elif args.notice:
            show_notice(client)
        else:
            # 默认显示仪表盘
            show_dashboard(client)

    except Exception as e:
        print(f"\n错误: {e}")
        if "未授权" in str(e) or "401" in str(e):
            print("Token 可能已过期，请重新登录：python3 yjb_tool.py --login")
        sys.exit(1)


if __name__ == '__main__':
    main()