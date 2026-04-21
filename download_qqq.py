"""
QQQ 历史数据下载脚本
===================
从雅虎财经下载 QQQ 完整上市至今的日线 OHLCV 数据，保存为回测框架兼容的 CSV 格式。

支持三种方式（按优先级自动降级）：
  1. yfinance         —— 最推荐，一行安装，速度快
  2. urllib 直连雅虎  —— 无需额外依赖，作为备用
  3. 手动下载指引     —— 以上都失败时打印操作步骤

用法：
  pip install yfinance          # 推荐，仅一次
  python download_qqq.py

输出：
  QQQ.csv  ——  与回测框架（run_phase1.py 等）直接兼容

CSV 格式示例：
  Date,Open,High,Low,Close,Adj Close,Volume
  1999-03-10,44.25,44.75,44.06,44.56,43.12,123456
  ...
"""

from __future__ import annotations
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
TICKER        = "QQQ"
START_DATE    = "1999-01-01"          # QQQ 上市日期 1999-03-10，往前留余量
END_DATE      = date.today().strftime("%Y-%m-%d")
OUTPUT_FILE   = Path("QQQ.csv")
YAHOO_TIMEOUT = 30                    # 秒


# ---------------------------------------------------------------------------
# 方式一：yfinance（推荐）
# ---------------------------------------------------------------------------
def download_yfinance() -> bool:
    try:
        import yfinance as yf
    except ImportError:
        print("[yfinance] 未安装。运行: pip install yfinance")
        return False

    print(f"[yfinance] 下载 {TICKER} {START_DATE} → {END_DATE} ...")
    ticker = yf.Ticker(TICKER)
    df = ticker.history(
        start=START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=False,   # 保留 Adj Close 列，与回测框架兼容
        actions=False,
    )

    if df.empty:
        print("[yfinance] 返回空数据，可能是网络问题。")
        return False

    # yfinance 返回的列名含大写空格，标准化
    df.index.name = "Date"
    df.index = df.index.tz_localize(None)   # 去掉时区后缀

    # 只保留需要的列
    keep = [c for c in ("Open","High","Low","Close","Adj Close","Volume")
            if c in df.columns]
    df = df[keep]

    df.to_csv(OUTPUT_FILE)
    print(f"[yfinance] ✓ 保存到 {OUTPUT_FILE}  ({len(df)} 行)")
    _print_summary(df)
    return True


# ---------------------------------------------------------------------------
# 方式二：urllib 直连雅虎财经 v8 API（无额外依赖）
# ---------------------------------------------------------------------------
def download_urllib() -> bool:
    """
    使用 Yahoo Finance v8 download endpoint。
    不需要 yfinance，但依赖雅虎的反爬策略，成功率低于 yfinance。
    """
    import csv, io

    # 转换日期为 Unix timestamp
    def to_ts(d: str) -> int:
        return int(datetime.strptime(d, "%Y-%m-%d").timestamp())

    t1 = to_ts(START_DATE)
    t2 = to_ts(END_DATE)
    url = (f"https://query1.finance.yahoo.com/v7/finance/download/{TICKER}"
           f"?period1={t1}&period2={t2}&interval=1d&events=history&includeAdjustedClose=true")

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    print(f"[urllib] 下载 {TICKER}（直连雅虎 API）...")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=YAHOO_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"[urllib] HTTP {e.code}：{e.reason}。雅虎可能触发了反爬。")
        return False
    except urllib.error.URLError as e:
        print(f"[urllib] 网络错误：{e.reason}")
        return False

    lines = raw.strip().splitlines()
    if len(lines) < 5:
        print("[urllib] 返回行数不足，数据可能为空。")
        return False

    OUTPUT_FILE.write_text(raw)
    print(f"[urllib] ✓ 保存到 {OUTPUT_FILE}  ({len(lines)-1} 行)")

    # 打印摘要
    import csv as csvmod, io
    reader = csvmod.DictReader(io.StringIO(raw))
    rows = list(reader)
    if rows:
        print(f"  首行日期: {rows[0].get('Date','?')}  |  "
              f"末行日期: {rows[-1].get('Date','?')}  |  "
              f"末行收盘: {rows[-1].get('Close','?')}")
    return True


# ---------------------------------------------------------------------------
# 方式三：手动下载指引
# ---------------------------------------------------------------------------
def print_manual_instructions():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║              手动下载 QQQ 历史数据（自动下载失败时使用）              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  方法 A：雅虎财经网页下载                                             ║
║  1. 打开 https://finance.yahoo.com/quote/QQQ/history/                ║
║  2. 点击右上角 "Download" 按钮                                        ║
║  3. 在弹窗中选择 Max（从上市至今）                                    ║
║  4. 下载后将文件重命名为 QQQ.csv                                      ║
║  5. 与回测脚本放在同一目录                                            ║
║                                                                      ║
║  方法 B：安装 yfinance 后重试                                         ║
║    pip install yfinance                                               ║
║    python download_qqq.py                                            ║
║                                                                      ║
║  方法 C：barchart.com（免费，需注册）                                 ║
║    https://www.barchart.com/stocks/quotes/QQQ/historical-download   ║
║    选择 Daily，Date Range: Earliest Available                         ║
║    Export → 保存为 QQQ.csv                                           ║
║                                                                      ║
║  CSV 格式要求（任一来源均可，字段名不区分大小写）：                    ║
║    Date, Open, High, Low, Close, Adj Close, Volume                   ║
║    日期格式: YYYY-MM-DD                                              ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


# ---------------------------------------------------------------------------
# 辅助：打印摘要
# ---------------------------------------------------------------------------
def _print_summary(df):
    try:
        import pandas as pd
        print(f"  首行: {df.index[0].date()}  收盘 {df['Close'].iloc[0]:.2f}")
        print(f"  末行: {df.index[-1].date()}  收盘 {df['Close'].iloc[-1]:.2f}")
        print(f"  总行数: {len(df)}")
        # 验证无大量缺失
        missing = df['Close'].isna().sum()
        if missing > 0:
            print(f"  ⚠ 收盘价缺失 {missing} 行")
        else:
            print(f"  ✓ 数据完整")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 下载完成后的格式校验 + 修复
# ---------------------------------------------------------------------------
def validate_and_fix():
    """
    读取保存的 CSV，做基本校验，若列名有差异则标准化，
    并追加 Adj Close 列（若原数据没有）。
    """
    try:
        import pandas as pd
    except ImportError:
        print("[校验] pandas 未安装，跳过格式校验。")
        return

    df = pd.read_csv(OUTPUT_FILE, parse_dates=["Date"]).set_index("Date")

    # 标准化列名（大小写、空格）
    rename = {}
    for col in df.columns:
        c = col.strip()
        if c.lower() == "adj close":
            rename[col] = "Adj Close"
        elif c.lower() in ("open","high","low","close","volume"):
            rename[col] = c.capitalize()
    if rename:
        df.rename(columns=rename, inplace=True)

    # 若无 Adj Close，用 Close 代替（回测框架会自动 fallback）
    if "Adj Close" not in df.columns and "Close" in df.columns:
        df["Adj Close"] = df["Close"]
        print("[校验] 未找到 Adj Close 列，已用 Close 填充。")

    # 过滤掉收盘价为 0 或 NaN 的行
    original_len = len(df)
    df = df[df["Close"] > 0].dropna(subset=["Close"])
    if len(df) < original_len:
        print(f"[校验] 移除了 {original_len - len(df)} 行无效数据。")

    df.sort_index(inplace=True)
    df.to_csv(OUTPUT_FILE)

    print(f"[校验] ✓ 文件已标准化：{OUTPUT_FILE}  "
          f"({len(df)} 行，{df.index[0].date()} – {df.index[-1].date()})")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print(f"  QQQ 历史数据下载器")
    print(f"  目标文件: {OUTPUT_FILE.resolve()}")
    print("=" * 60 + "\n")

    # 按优先级尝试
    success = False

    if not success:
        success = download_yfinance()

    if not success:
        print()
        success = download_urllib()

    if not success:
        print_manual_instructions()
        sys.exit(1)

    # 成功后校验格式
    print()
    validate_and_fix()

    print(f"\n完成。将 {OUTPUT_FILE} 放在回测脚本同目录，然后运行:\n"
          f"  python run_phase1.py\n")


if __name__ == "__main__":
    main()
