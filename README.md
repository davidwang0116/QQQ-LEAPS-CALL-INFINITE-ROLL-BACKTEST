# QQQ LEAPS Call Infinite Roll Strategy Backtest
# QQQ 远期看涨期权无限展期策略回测

A full-featured backtesting framework for a QQQ LEAPS Call option strategy. Supports **real QQQ price data** (Yahoo Finance CSV) with BSM and Merton Jump-Diffusion (MJD) option pricing models. All strategy parameters — including entry and harvest delta thresholds — are tunable.

基于真实 QQQ 历史数据的 LEAPS Call 期权策略全功能回测框架，支持 BSM 和 MJD 两种定价模型，入场与收割 Delta 阈值等所有参数均可调节。

---

## Strategy Rules · 策略规则

| Rule · 规则 | Trigger · 触发条件 | Action · 操作 |
|---|---|---|
| **Entry · 入场** | Open ≤ prev close × (1 − 1%) · 开盘价 ≤ 前收盘 × 99% | Buy the latest quarterly LEAPS Call, DTE in [650, 800], at target delta (default 0.70), sized by cash tier · 买入 DTE 在 [650, 800] 内最晚季度 LEAPS Call，目标 Delta=0.70，按现金分级确定规模 |
| **Cash sizing · 现金分级** | cash > 40% / 10% < cash ≤ 40% / cash ≤ 10% | Deploy 10% / 5% / skip · 动用 10% / 5% 现金，或跳过 |
| **Harvest roll · 收割展期** | Any position delta ≥ harvest threshold (default 0.90) · 任一持仓 Delta ≥ 0.90 | Sell and re-open same contract count in a new 650–800d, target-delta LEAPS · 卖出并以相同合约数重开 650–800 天新 LEAPS |
| **Forced roll · 强制展期** | Remaining DTE ≤ 300, not yet harvested · 剩余 DTE ≤ 300 天且未被收割 | Roll to next quarterly expiry ≥ 650 DTE — skipped entirely if cash is insufficient to open even 1 new contract · 展期至下一个 ≥650 天季度到期日；若现金不足以买入哪怕 1 张新合约，则跳过本次展期，保留原仓位 |
| **Counter-trend snipe · 逆势狙击** | Any held delta < 0.50 AND cash > 10% AND 30-day cooldown elapsed · 任一持仓 Delta < 0.50，且现金 > 10%，且已过 30 天冷却期 | Enter per cash-tier sizing, even without a 1% gap-down · 即使无 1% 跳空缺口，也按现金分级规则入场 |

Expirations use the 3rd Friday of March / June / September / December.
到期日采用每年 3 / 6 / 9 / 12 月的第三个周五。

---

## Backtest Results · 回测结果

> Real QQQ data, $100,000 starting capital · 真实 QQQ 数据，起始资金 $100,000

### Summary by Start Year · 各起始年度汇总

| Start · 起始年 | Model · 模型 | Strategy CAGR · 策略年化 | QQQ CAGR | Max DD · 最大回撤 | QQQ Max DD | Sharpe | Final Value · 最终值 |
|---|---|---|---|---|---|---|---|
| 2000 | BSM | **17.91%** | 8.59% | −100.0% | −83.0% | 0.81 | $7,527,796 |
| 2000 | MJD | 13.79% | 8.59% | −100.0% | −83.0% | 0.58 | $2,955,408 |
| 2005 | BSM | **36.09%** | 15.02% | −94.9% | −53.4% | 0.76 | $70,415,592 |
| 2005 | MJD | 29.47% | 15.02% | −94.0% | −53.4% | 0.71 | $24,392,077 |
| 2010 | BSM | **54.54%** | 18.61% | −74.6% | −35.1% | **1.00** | $119,670,515 |
| 2010 | MJD | 45.40% | 18.61% | −72.7% | −35.1% | 0.94 | $44,340,499 |
| 2020 | BSM | **48.05%** | 19.89% | −66.9% | −35.1% | 0.92 | $1,174,312 |
| 2020 | MJD | 40.36% | 19.89% | −62.6% | −35.1% | 0.88 | $840,096 |

### BSM vs MJD — Side by Side · BSM 与 MJD 对比

| Start · 起始年 | BSM CAGR | MJD CAGR | BSM MaxDD | MJD MaxDD | BSM Sharpe | MJD Sharpe | QQQ CAGR |
|---|---|---|---|---|---|---|---|
| 2000 | 17.91% | 13.79% | −100.0% | −100.0% | 0.81 | 0.58 | 8.59% |
| 2005 | 36.09% | 29.47% | −94.9% | −94.0% | 0.76 | 0.71 | 15.02% |
| 2010 | 54.54% | 45.40% | −74.6% | −72.7% | 1.00 | 0.94 | 18.61% |
| 2020 | 48.05% | 40.36% | −66.9% | −62.6% | 0.92 | 0.88 | 19.89% |

**Key observations · 核心观察：**

- **The 2000 scenario now recovers.** After fixing the forced-roll engine bug (see [Changelog](#changelog--更新记录) below), the strategy no longer leaves orphaned closed positions when cash is insufficient to open a new contract. Instead it holds the existing position. This allows the 2000 scenario to survive the dot-com crash and GFC, eventually compounding to **$7.5M (BSM) / $2.95M (MJD)** — beating QQQ B&H (+17.91% vs +8.59% CAGR) despite a −100% intra-period drawdown.
  **2000 年场景现已能够恢复。** 修复强制展期 engine bug 后（详见[更新记录](#changelog--更新记录)），策略在现金不足时不再孤立平仓，而是保留原仓位继续持有。这使 2000 年场景得以熬过科网崩盘和金融危机，最终累计至 **$7.5M（BSM）/ $295万（MJD）**，CAGR 跑赢 QQQ（17.91% vs 8.59%），尽管期间曾经历 −100% 的区间内最大回撤。

- **MJD prices options ~10–15% higher than BSM** (jump-risk premium) → fewer contracts per dollar → lower CAGR, slightly lower MaxDD across all scenarios.
  **MJD 期权定价比 BSM 高约 10–15%**（跳跃风险溢价）→ 同等资金购入合约数更少 → 全部场景的年化收益均偏低，最大回撤也略低。

- **Strategy consistently beats QQQ buy-and-hold CAGR across all start years**, at the cost of significantly higher drawdowns.
  **策略在全部起始年度均跑赢 QQQ 买入持有**，代价是显著更大的最大回撤。

### Delta Sensitivity — 2020 Start, BSM · Delta 敏感性分析（2020 年起始，BSM，完整 6×5 网格）

| entry_delta | harvest_delta | CAGR | Max DD · 最大回撤 | Sharpe |
|---|---|---|---|---|
| **0.55** | **0.80** | **55.7%** | −74.8% | 0.92 ← best CAGR · 最优收益 |
| 0.60 | 0.85 | 55.5% | −71.8% | **0.94** ← best Sharpe · 最优 Sharpe |
| 0.55 | 0.90 | 54.2% | −74.6% | 0.91 |
| **0.70** | **0.90** *(default · 默认)* | 48.0% | −66.9% | 0.92 |
| 0.80 | 0.95 | 39.9% | **−61.4%** | 0.91 ← lowest MaxDD · 最低回撤 |

**Key finding · 核心发现：** After the engine fix, lower entry delta (0.55–0.60) + earlier harvest (0.80–0.85) continues to dominate the default by ~7–8 pp of CAGR, with better Sharpe ratios across the board.
Engine 修复后，较低入场 Delta（0.55–0.60）搭配较早收割（0.80–0.85）仍然以约 7–8 个百分点的 CAGR 优势领先默认参数，且各处 Sharpe 比率均有改善。

### Delta Sensitivity — 2010 Start, BSM · Delta 敏感性分析（2010 年起始，BSM，粗粒度 3×2 网格）

| entry_delta | harvest_delta | CAGR | Max DD · 最大回撤 | Sharpe |
|---|---|---|---|---|
| **0.60** | **0.90** | **61.5%** | −80.2% | **1.01** ← best overall · 综合最优 |
| 0.60 | 0.80 | 60.8% | −80.0% | 1.00 |
| 0.70 | 0.90 *(default · 默认)* | 54.5% | −74.6% | 1.00 |
| 0.70 | 0.80 | 53.7% | −74.1% | 0.99 |
| 0.80 | 0.90 | 50.8% | **−70.2%** | 1.02 ← best Sharpe · 最优 Sharpe |

---

## Changelog · 更新记录

### v1.1 — Engine bug fix: forced roll no longer creates orphaned closes
### v1.1 — Engine 修复：强制展期不再产生孤立平仓

**Problem · 问题：** In the original `engine.py`, `_roll_position()` would sell the existing position first, then attempt to buy the new one. If cash was insufficient to open even a single new contract, the function returned early — leaving the old position closed with no replacement. This produced spurious `CLOSE` events mid-backtest (visible in 2020–2022 and 2023 periods), and was the primary cause of the 2000 scenario failing to recover.

原始 `engine.py` 中，`_roll_position()` 先卖出旧仓位，再尝试买入新合约。若现金不足以买入哪怕一张新合约，函数提前返回——导致旧仓位已平但无替代仓位，在回测中途产生虚假的 `CLOSE` 事件（2020–2022 及 2023 年间均有出现），也是 2000 年场景无法恢复的根本原因。

**Fix · 修复：** Affordability is now checked **before** any position is touched. If the estimated proceeds from closing the old position plus available cash cannot cover the cost of at least one new contract, the entire roll is skipped and the position is left unchanged.

现在在触动任何仓位之前先进行可行性检查。若预估的旧仓位平仓收益加上当前现金仍不足以购入至少一张新合约，则整个展期操作被跳过，仓位保持不变。

```python
# engine.py: _roll_position() — key change
# Estimate proceeds BEFORE selling
bid = self._apply_slippage(pos.current_price, "sell")
estimated_proceeds = bid * 100 * pos.contracts - commission * pos.contracts
available = self.cash + estimated_proceeds
n_ct = old_contracts if affordable else int(available // per_ct)

if n_ct <= 0:
    return  # Can't afford any new contract — leave position as-is
            # 买不起任何新合约——保留原仓位不动

# Only now is it safe to sell and re-open
proceeds = self._sell_position(...)
```

---

## Quick Start · 快速开始

```bash
pip install pandas numpy scipy matplotlib

# Download QQQ historical data from Yahoo Finance, save as QQQ.csv
# 从 Yahoo Finance 下载 QQQ 历史数据，保存为 QQQ.csv
# Required columns · 必要列: Date, Open, High, Low, Close, Adj Close

python run_phase1.py   # ~3 min  — 4 start-years × 2 models · 4 起始年 × 2 定价模型
python run_phase2.py   # ~10 sec — all plots and CSVs · 生成全部图表与汇总表
python run_phase3.py   # ~80 sec — delta sensitivity sweep · Delta 敏感性扫描
```

---

## File Structure · 文件结构

### Core Modules · 核心模块

| File · 文件 | Purpose · 功能 |
|---|---|
| `config.py` | All tunable parameters — delta thresholds, DTE window, cash tiers, friction costs, MJD parameters · 所有可调参数：Delta 阈值、DTE 窗口、现金分级、摩擦成本、MJD 参数 |
| `pricing.py` | BSM and MJD (Merton 1976 closed-form series) pricing; delta→strike Brent solver; `scipy.special.ndtr` for ~15× speed vs `norm.cdf` · BSM 和 MJD（Merton 1976 闭式级数）定价；Delta→行权价 Brent 反解；用 `scipy.special.ndtr` 提速约 15× |
| `data.py` | Real CSV loader with Adj Close back-adjustment; piecewise risk-free rate curve (2000–2026) · 真实 CSV 加载（含复权处理）；2000–2026 年分段无风险利率曲线 |
| `options.py` | 3rd-Friday quarterly expiration finder; DTE-window selector; `OptionPosition` dataclass · 季度到期日查找（每季度第三个周五）；DTE 窗口选择；`OptionPosition` 数据类 |
| `engine.py` | Backtest engine — all four strategy rules, per-day mark-to-market, equity curve, trade log · 回测引擎：四条策略规则、逐日盯市、权益曲线、交易日志 |
| `reports.py` | Summary tables; 4-panel detail charts (equity, drawdown, cash%, positions/delta); delta sensitivity heatmaps · 汇总表；4-panel 详情图（权益、回撤、现金比例、持仓数/Delta）；Delta 敏感性热力图 |

### Runner Scripts · 运行脚本

| File · 文件 | Purpose · 功能 |
|---|---|
| `run_phase1.py` | Runs the 4×2 scenario grid and pickles results to `_cache/` · 运行 4×2 场景网格，将结果 pickle 至 `_cache/` |
| `run_phase2.py` | Loads phase-1 cache, generates all plots and CSV outputs · 加载阶段一缓存，生成全部图表与 CSV 输出 |
| `run_phase3.py` | Delta sensitivity sweep (2020: full 6×5 BSM; 2010: coarse 3×2 BSM) · Delta 敏感性扫描（2020 年：完整 6×5；2010 年：粗粒度 3×2） |
| `run_trade_report.py` | Generates a full bilingual trade-by-trade Markdown log for the 2015 start scenario · 生成 2015 年起始场景的完整逐笔交易明细 Markdown 报告 |
| `main.py` | Chains all three phases · 串联三个阶段 |

### Outputs Generated · 生成的输出文件

| File · 文件 | Content · 内容 |
|---|---|
| `qqq_leaps_summary.csv` | Full metrics for all 8 scenarios · 8 个场景的完整指标 |
| `qqq_leaps_BSM_vs_MJD.csv` | BSM/MJD side-by-side comparison · BSM 与 MJD 并排对比 |
| `qqq_leaps_scenarios_BSM.png` | 2×2 equity curve comparison (BSM) · 2×2 权益曲线对比图（BSM） |
| `qqq_leaps_scenarios_MJD.png` | 2×2 equity curve comparison (MJD) · 2×2 权益曲线对比图（MJD） |
| `qqq_leaps_detail_{year}_{model}.png` | 4-panel detail chart per scenario · 每个场景的 4-panel 详情图 |
| `qqq_leaps_delta_sens_{year}_{metric}.png` | CAGR / MaxDD / Sharpe heatmaps · CAGR / MaxDD / Sharpe 热力图 |
| `qqq_leaps_delta_sensitivity_{year}.csv` | Sensitivity grid values · 敏感性网格数值 |
| `qqq_leaps_trades_2020_BSM.csv` | Full trade log for 2020 BSM · 2020 BSM 完整交易日志 |
| `qqq_leaps_equity_2020_BSM.csv` | Daily equity curve for 2020 BSM · 2020 BSM 逐日权益曲线 |
| `qqq_leaps_trade_report.md` | Trade-by-trade log for 2015 start, with mode labels · 2015 年起始逐笔交易明细，含交易模式标注 |

---

## Configuration Reference · 参数说明 (`config.py`)

```python
# ── Entry / Harvest thresholds · 入场与收割 Delta 阈值 ──────────────────────
entry_delta          = 0.70    # Target delta when opening a position · 入场目标 Delta
harvest_delta        = 0.90    # Roll trigger when delta rises to this level · 收割触发 Delta

# ── DTE window · DTE 窗口 ────────────────────────────────────────────────────
dte_min              = 650     # Minimum DTE for new LEAPS · 新 LEAPS 最短 DTE
dte_max              = 800     # Maximum DTE for new LEAPS · 新 LEAPS 最长 DTE
forced_roll_dte      = 300     # Forced roll if DTE drops here · 触发强制展期的剩余 DTE

# ── Entry trigger · 入场触发条件 ────────────────────────────────────────────
gap_down_threshold   = -0.01   # Open ≤ prev close × (1 − 1%) · 开盘跌幅阈值

# ── Cash-tiered sizing · 现金分级仓位 ───────────────────────────────────────
cash_tier_high       = 0.40    # cash > 40%  → deploy size_high · 现金 > 40% 时用 size_high
cash_tier_low        = 0.10    # cash > 10%  → deploy size_mid; ≤ 10% → skip · 现金 > 10% 用 size_mid；≤ 10% 跳过
size_high            = 0.10    # 10% of cash · 动用 10% 现金
size_mid             = 0.05    #  5% of cash · 动用 5% 现金

# ── Counter-trend snipe · 逆势狙击 ──────────────────────────────────────────
snipe_delta          = 0.50    # Trigger if any held position delta < this · 任一持仓 Delta 低于此值触发
snipe_cash_min       = 0.10    # Require cash > 10% · 要求现金 > 10%
snipe_cooldown_days  = 30      # Minimum days between snipes · 两次狙击最短间隔天数

# ── Pricing model · 定价模型 ─────────────────────────────────────────────────
pricing_model        = "bsm"   # "bsm" or "mjd" · 选择 "bsm" 或 "mjd"

# ── IV proxy · 隐含波动率代理 ───────────────────────────────────────────────
iv_window_days       = 60      # Rolling realized vol window · 滚动实现波动率计算窗口
iv_vrp               = 0.03    # +3% volatility risk premium · +3% 波动率风险溢价
iv_floor             = 0.15
iv_cap               = 0.80

# ── MJD jump-diffusion parameters · MJD 跳扩散参数 ──────────────────────────
mjd_lambda           = 1.2     # Jump intensity (jumps per year) · 跳跃强度（每年次数）
mjd_jump_mean        = -0.05   # Mean log-jump size · 对数跳跃均值
mjd_jump_std         = 0.12    # Std of log-jump size · 对数跳跃标准差

# ── Market frictions · 市场摩擦成本 ─────────────────────────────────────────
commission_per_contract = 0.65
slippage_bps            = 25
```

---

## Option Pricing · 期权定价说明

**BSM (Black-Scholes-Merton):** Closed-form, fast. Uses `scipy.special.ndtr` instead of `scipy.stats.norm.cdf` for ~15× speedup. Delta→strike inversion via Brent's method with progressively widening brackets.
经典闭式解，速度快。使用 `scipy.special.ndtr` 替代 `scipy.stats.norm.cdf`，提速约 15×。Delta→行权价通过逐步收窄括号区间的 Brent 法反解。

**MJD (Merton Jump-Diffusion):** Merton (1976) Poisson series:
Merton（1976）泊松级数：

$$C_{MJD} = \sum_{n=0}^{\infty} e^{-\lambda' T} \frac{(\lambda' T)^n}{n!} \cdot C_{BSM}(S, K, T, r_n, q, \sigma_n)$$

Each term adds the effect of $n$ jumps via adjusted drift $r_n$ and volatility $\sigma_n$. Series terminates when Poisson weight < 1e-10. Jump risk premium makes MJD options ~10–15% more expensive than BSM at equivalent delta, resulting in fewer contracts per dollar and lower realized leverage.
每一项通过调整后的漂移率 $r_n$ 和波动率 $\sigma_n$ 叠加 $n$ 次跳跃的影响。泊松权重低于 1e-10 时级数截断。跳跃风险溢价使 MJD 期权在相同 Delta 下比 BSM 贵约 10–15%，同等资金购入合约数更少，实际杠杆倍数更低。

**IV proxy · 隐含波动率代理：** `IV = rolling_realized_vol(60d) + 3% VRP`, clamped to [15%, 80%]. Applied uniformly across the term structure — real LEAPS IV is typically 3–8 pp below short-dated ATM IV, so this proxy slightly overestimates option cost (conservative bias).
`IV = 60 日滚动实现波动率 + 3% VRP`，限制在 [15%, 80%]。对期限结构统一应用——真实 LEAPS IV 通常比短期 ATM IV 低 3–8 个百分点，因此该代理略高估期权成本（偏保守）。

**Risk-free rate · 无风险利率：** Piecewise approximation of the US 2-year yield, 2000–2026 (range: 0.2% COVID trough → 6.2% 2000 peak).
2000–2026 年美国 2 年期国债收益率的分段近似（范围：0.2% COVID 低谷 → 6.2% 2000 年峰值）。

---

## Known Limitations · 已知限制

### 1. Large MaxDD is expected · 大幅回撤属正常现象

QQQ fell 45% in the 2022 bear market. The strategy carries ~2–3× delta-leverage → strategy fell ~65–75%. This is the mechanical consequence of unhedged long LEAPS. Even the 2000 scenario, which experiences a near-complete wipeout during the dot-com crash, ultimately recovers due to continued buying at depressed prices and compounding through the subsequent bull market — achieving **17.91% CAGR vs QQQ's 8.59%** over 26 years.
2022 年熊市 QQQ 跌幅约 45%，策略持有约 2–3 倍 Delta 杠杆，因此策略回撤约 65–75%。这是无对冲 LEAPS 多头的固有特性。即便是 2000 年场景——在科网崩盘期间几乎全军覆没——也因在低位持续买入并经历后续牛市的复利效应而最终恢复，26 年间实现 **17.91% CAGR vs QQQ 的 8.59%**。

### 2. Unlimited position accumulation · 持仓数量无上限

Long bull runs accumulate 200+ open lots. To cap this:
长期牛市中可累积 200 个以上持仓。如需限制：
```python
# config.py
max_positions: int = 50

# engine.py: _execute_entry_rule
if len(self.positions) >= self.cfg.max_positions:
    return False
```

### 3. IV proxy is not a real option chain · IV 代理不等同于真实期权链

For production use, replace rolling realized vol + VRP with actual LEAPS market quotes.
如用于实盘，请将滚动实现波动率 + VRP 替换为真实 LEAPS 市场报价。

---

## Custom Backtest Example · 自定义回测示例

```python
from config import StrategyConfig
from engine import BacktestEngine
from data import load_qqq_csv
import pandas as pd

price_df = load_qqq_csv("QQQ.csv")

cfg = StrategyConfig(
    pricing_model="bsm",
    entry_delta=0.60,        # lower entry delta for higher gamma exposure · 较低入场 Delta，更高 Gamma 暴露
    harvest_delta=0.85,      # harvest earlier to reduce roll churn · 更早收割，减少换仓摩擦
    gap_down_threshold=-0.015,
)

eng = BacktestEngine(
    price_df, cfg,
    start=pd.Timestamp("2015-01-02"),
    end=pd.Timestamp("2026-04-20"),
    initial_cash=100_000,
)
res = eng.run()
print(res.metrics())
```

---

## Requirements · 环境依赖

```
pandas>=1.5
numpy>=1.23
scipy>=1.10
matplotlib>=3.6
```

```bash
pip install pandas numpy scipy matplotlib
```

---

## Data Source · 数据来源

Download QQQ historical prices from [Yahoo Finance](https://finance.yahoo.com/quote/QQQ/history/) as a CSV file. The loader handles Adj Close back-adjustment automatically.
从 [Yahoo Finance](https://finance.yahoo.com/quote/QQQ/history/) 下载 QQQ 历史行情 CSV 文件，加载器会自动处理复权（Adj Close）。

Expected columns · 必要列：`Date, Open, High, Low, Close, Adj Close`

---

## Acknowledgement · 致谢
 
This project was inspired by a video from YouTube creator **天哥复利之道**, whose clear and insightful explanation of the LEAPS Call infinite-roll concept sparked the idea for building this backtest framework.
 
本项目的灵感来源于油管博主**天哥复利之道**的视频。他对 LEAPS Call 无限展期策略清晰而深入的讲解，直接启发了这个回测框架的构建。
 
▶ [天哥复利之道 — LEAPS Call 无限展期策略](https://www.youtube.com/watch?v=Zjy3-FLYJSo)

## Disclaimer · 免责声明

This project is for **research and educational purposes only**. Past backtest results — even on real historical data — do not guarantee future performance. LEAPS options involve significant leverage and can result in total loss of capital. Nothing in this repository constitutes financial advice.

本项目仅供**研究与学习使用**。历史回测结果——即便基于真实数据——不代表未来表现。LEAPS 期权具有显著杠杆效应，可能导致本金全部损失。本仓库内容不构成任何投资建议。