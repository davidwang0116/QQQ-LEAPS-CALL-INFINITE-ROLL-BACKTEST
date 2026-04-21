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
| **Forced roll · 强制展期** | Remaining DTE ≤ 300, not yet harvested · 剩余 DTE ≤ 300 天且未被收割 | Spend cash to roll to next quarterly expiry ≥ 650 DTE · 花现金展期至下一个 ≥650 天季度到期日 |
| **Counter-trend snipe · 逆势狙击** | Any held delta < 0.50 AND cash > 10% AND 30-day cooldown elapsed · 任一持仓 Delta < 0.50，且现金 > 10%，且已过 30 天冷却期 | Enter per cash-tier sizing, even without a 1% gap-down · 即使无 1% 跳空缺口，也按现金分级规则入场 |

Expirations use the 3rd Friday of March / June / September / December.
到期日采用每年 3 / 6 / 9 / 12 月的第三个周五。

---

## Backtest Results · 回测结果

> Real QQQ data, $100,000 starting capital · 真实 QQQ 数据，起始资金 $100,000

### Summary by Start Year · 各起始年度汇总

| Start · 起始年 | Model · 模型 | Strategy CAGR · 策略年化 | QQQ CAGR | Total Return · 总收益 | Max DD · 最大回撤 | QQQ Max DD | Sharpe | Final Value · 最终值 |
|---|---|---|---|---|---|---|---|---|
| 2000 | BSM | −18.01% | 8.59% | −99.5% | −99.5% | −83.0% | −0.20 | $536 |
| 2000 | MJD | −18.12% | 8.59% | −99.5% | −99.7% | −83.0% | −0.19 | $518 |
| 2005 | BSM | **35.86%** | 15.02% | **67,865%** | −94.6% | −53.4% | 0.76 | $67,964,630 |
| 2005 | MJD | 28.73% | 15.02% | 21,489% | −93.9% | −53.4% | 0.70 | $21,588,861 |
| 2010 | BSM | **54.52%** | 18.61% | **119,258%** | −74.6% | −35.1% | **1.00** | $119,357,859 |
| 2010 | MJD | 45.36% | 18.61% | 44,047% | −72.7% | −35.1% | 0.94 | $44,147,001 |
| 2020 | BSM | **46.09%** | 19.89% | 980% | −65.9% | −35.1% | 0.91 | $1,079,973 |
| 2020 | MJD | 39.40% | 19.89% | 705% | −62.6% | −35.1% | 0.87 | $804,600 |

### BSM vs MJD — Side by Side · BSM 与 MJD 对比

| Start · 起始年 | BSM CAGR | MJD CAGR | BSM MaxDD | MJD MaxDD | BSM Sharpe | MJD Sharpe |
|---|---|---|---|---|---|---|
| 2000 | −18.01% | −18.12% | −99.5% | −99.7% | −0.20 | −0.19 |
| 2005 | 35.86% | 28.73% | −94.6% | −93.9% | 0.76 | 0.70 |
| 2010 | 54.52% | 45.36% | −74.6% | −72.7% | 1.00 | 0.94 |
| 2020 | 46.09% | 39.40% | −65.9% | −62.6% | 0.91 | 0.87 |

**Key observations · 核心观察：**

- **MJD prices options ~10–15% higher than BSM** (jump-risk premium) → fewer contracts per dollar → lower CAGR, slightly lower MaxDD
  **MJD 期权定价比 BSM 高约 10–15%**（跳跃风险溢价）→ 同等资金购入合约数更少 → 年化收益更低，最大回撤也略低

- **2000 start is a near-total wipeout.** The dot-com crash (QQQ −83%) then the 2008 GFC destroyed all early positions before reaching harvest delta. Only 3 harvest rolls triggered in 26 years vs ~95/year in the 2005 scenario. See [Known Limitations](#known-limitations--已知限制与改进建议) for the failure mechanism and suggested fixes.
  **2000 年起始几乎全军覆没。** 科网泡沫破灭（QQQ 跌 83%）加上 2008 年金融危机，将所有早期持仓在触达收割 Delta 之前摧毁殆尽。26 年内仅触发 3 次收割展期，而 2005 场景年均高达 95 次。详见[已知限制与改进建议](#known-limitations--已知限制与改进建议)。

- **Strategy consistently beats QQQ buy-and-hold CAGR (2005–2020)**, at the cost of significantly higher drawdowns.
  **2005–2020 年间，策略年化收益持续跑赢 QQQ 买入持有**，代价是显著更大的最大回撤。

### Delta Sensitivity — 2020 Start, BSM · Delta 敏感性分析（2020 年起始，BSM，完整 6×5 网格）

| entry_delta | harvest_delta | CAGR | Max DD · 最大回撤 | Sharpe |
|---|---|---|---|---|
| **0.55** | **0.80** | **54.5%** | −75.4% | 0.87 |
| 0.55 | 0.90 | 51.1% | −73.7% | 0.89 |
| 0.60 | 0.85 | 53.2% | −71.4% | **0.92** ← best Sharpe · 最优 Sharpe |
| **0.70** | **0.90** *(default · 默认)* | 46.1% | −65.9% | 0.91 |
| 0.80 | 0.95 | 38.1% | **−61.0%** | 0.89 ← lowest MaxDD · 最低回撤 |

**Key finding · 核心发现：** Lower entry delta (0.55–0.60) + earlier harvest (0.80–0.85) dominates the default (0.70/0.90) by ~8 percentage points of CAGR. The lower entry delta buys cheaper, higher-gamma contracts; the earlier harvest threshold locks in profits faster and reduces roll churn.
入场 Delta 较低（0.55–0.60）搭配较早收割（0.80–0.85），比默认参数（0.70/0.90）年化收益高出约 8 个百分点。较低的入场 Delta 买到更便宜、Gamma 更高的合约；较早的收割阈值更快锁定利润并减少换仓摩擦。

### Delta Sensitivity — 2010 Start, BSM · Delta 敏感性分析（2010 年起始，BSM，粗粒度 3×2 网格）

| entry_delta | harvest_delta | CAGR | Max DD · 最大回撤 | Sharpe |
|---|---|---|---|---|
| **0.60** | **0.90** | **61.5%** | −80.2% | **1.01** ← best overall · 综合最优 |
| 0.60 | 0.80 | 60.7% | −80.0% | 1.00 |
| 0.70 | 0.90 *(default · 默认)* | 54.5% | −74.6% | 1.00 |
| 0.70 | 0.80 | 53.7% | −74.1% | 0.99 |
| 0.80 | 0.90 | 50.8% | **−70.2%** | 1.02 ← best Sharpe · 最优 Sharpe |

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
| `qqq_leaps_trades_2020_BSM.csv` | Full trade log for 2020 BSM (472 trades) · 2020 BSM 完整交易日志（472 笔） |
| `qqq_leaps_equity_2020_BSM.csv` | Daily equity curve for 2020 BSM · 2020 BSM 逐日权益曲线 |

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

## Known Limitations and Suggested Fixes · 已知限制与改进建议

### 1. The 2000 scenario — failure mechanism · 2000 年场景——失败机制

The strategy has no drawdown protection. The exact failure sequence:
该策略没有任何回撤保护机制，具体失败过程如下：

1. **Initial wipeout (2000–2002) · 初始毁灭（2000–2002）：** QQQ fell 83%. Strike prices near $100 became deep OTM; all early positions decayed to near zero. Only 3 harvest rolls triggered in 26 years (vs ~95/year in the 2005 scenario) — meaning virtually no position ever recovered enough to hit the harvest delta threshold.
   QQQ 跌幅达 83%。行权价在 $100 附近的早期持仓全部变成深度虚值，Delta 趋近于零，权利金接近归零。26 年内仅触发 3 次收割展期（而 2005 场景年均约 95 次），说明几乎没有任何持仓能回到收割 Delta 阈值。

2. **Forced-roll cash burn · 强制展期烧钱：** 22 forced rolls spent remaining cash extending dying positions at low delta rather than cutting losses.
   22 次强制展期持续消耗剩余现金，将毫无希望的低 Delta 持仓一再展期，而非及时止损。

3. **Absolute dollar trap · 绝对金额陷阱：** Even with `cash_pct` appearing healthy, absolute cash fell below the cost of a single contract (~$3K–$8K), making `_contracts_affordable()` return 0. The strategy became permanently frozen.
   即使 `cash_pct`（现金占比）看似健康，现金绝对金额已跌至单张合约成本以下（约 $3K–$8K），导致 `_contracts_affordable()` 持续返回 0，策略彻底冻结，再无法入场。

**Suggested fix #1 — Size by portfolio value, not cash alone · 改进方案一：按组合净值而非仅凭现金定仓**
```python
# engine.py: _execute_entry_rule
pv = self.portfolio_value()
if pv * self.cfg.size_high < min_contract_cost:
    return False   # skip gracefully rather than burning micro-budget
                   # 优雅跳过，避免浪费微薄预算
budget = pv * sizing_fraction   # use total NAV, not just cash · 以组合净值为基准
budget = min(budget, self.cash) # still can't spend more than you have · 但不能超过可用现金
```

**Suggested fix #2 — Add a quality filter to forced rolls · 改进方案二：强制展期前加筛查**
```python
# Only force-roll if the position still has meaningful value
# 仅在持仓仍有价值时才强制展期
to_force = [p for p in self.positions
            if p.dte(date) <= cfg.forced_roll_dte
            and p.current_delta >= 0.30              # still has a chance · 仍有机会
            and p.market_value() >= 0.30 * p.entry_cost]  # hasn't lost > 70% · 未亏损超 70%
# Let deeply OTM expiring positions expire worthless (stop-loss by expiry)
# 深度虚值的到期持仓直接让其归零（到期止损）
```

**Suggested fix #3 — Trend filter (optional, high impact) · 改进方案三：趋势过滤器（可选，效果显著）**
```python
# config.py
trend_filter: bool = True
trend_sma_days: int = 200

# engine.py: in _step, before entry check · 在入场判断前执行
if cfg.trend_filter:
    sma200 = self.prices["Close"].rolling(cfg.trend_sma_days).mean().asof(date)
    if close_px < sma200 * 0.85:
        return  # don't enter when deeply below 200-day SMA · 价格深跌破 200 日均线时不入场
```

### 2. Large MaxDD is expected · 大幅回撤属正常现象

QQQ fell 45% in the 2022 bear market. The strategy carried ~2–3× delta-leverage → strategy fell ~65–75%. This is a mechanical consequence of unhedged long LEAPS. The 2010 scenario achieves a **1.00 Sharpe** despite −74.6% MaxDD because the long bull market dominates.
2022 年熊市 QQQ 跌幅约 45%，策略持有约 2–3 倍 Delta 杠杆，因此策略回撤约 65–75%。这是无对冲 LEAPS 多头的固有特性。尽管 2010 场景最大回撤达 −74.6%，但长期牛市行情主导了最终结果，Sharpe 仍高达 **1.00**。

### 3. Unlimited position accumulation · 持仓数量无上限

The spec does not cap position count. Long bull runs accumulate 200+ open lots (each gap-down opens a new lot). To cap this:
原始策略规则未限制持仓数量，长期牛市中可累积 200 个以上持仓（每次跳空缺口都开新仓）。如需限制：
```python
# config.py
max_positions: int = 50

# engine.py: _execute_entry_rule
if len(self.positions) >= self.cfg.max_positions:
    return False
```

### 4. IV proxy is not a real option chain · IV 代理不等同于真实期权链

When using real QQQ price data without actual option prices, the model uses rolling realized vol + VRP as the IV input. This is a reasonable approximation but does not replicate real-world term structure, skew, or intraday liquidity dynamics. For production use, replace with actual LEAPS market quotes.
使用真实 QQQ 价格数据但无实际期权报价时，模型以滚动实现波动率 + VRP 作为 IV 输入。这是合理的近似方案，但无法完整复现真实市场的期限结构、波动率偏斜或盘中流动性动态。如用于实盘，请替换为真实 LEAPS 市场报价。

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

## Disclaimer · 免责声明

This project is for **research and educational purposes only**. Past backtest results — even on real historical data — do not guarantee future performance. LEAPS options involve significant leverage and can result in total loss of capital. Nothing in this repository constitutes financial advice.

本项目仅供**研究与学习使用**。历史回测结果——即便基于真实数据——不代表未来表现。LEAPS 期权具有显著杠杆效应，可能导致本金全部损失。本仓库内容不构成任何投资建议。
