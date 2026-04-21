"""
Configuration for the QQQ LEAPS Call backtest.

All strategy parameters (including entry delta and harvest delta)
can be tuned here and at the BacktestEngine call site.
"""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class StrategyConfig:
    # ---- Entry rule ----
    gap_down_threshold: float = -0.01     # open return vs previous close <= -1%

    # Cash-tiered position sizing (fraction of current cash deployed)
    cash_tier_high: float = 0.40          # cash% > 40%
    cash_tier_low: float = 0.10           # cash% > 10%
    size_high: float = 0.10               # 10% of cash when cash > 40%
    size_mid: float = 0.05                # 5%  of cash when 10% < cash <= 40%

    # ---- Option selection ----
    dte_min: int = 650
    dte_max: int = 800
    entry_delta: float = 0.70             # target Delta at entry  (ADJUSTABLE)
    harvest_delta: float = 0.90           # roll threshold          (ADJUSTABLE)

    # ---- Forced roll ----
    forced_roll_dte: int = 300            # if DTE <= 300 and not harvested, force roll
    forced_roll_target_dte: int = 650     # roll target per spec

    # ---- Counter-trend sniping ----
    snipe_delta: float = 0.50             # if any position delta < 0.5
    snipe_cash_min: float = 0.10          # AND cash > 10%
    snipe_cooldown_days: int = 30         # cooldown between snipes

    # ---- Pricing ----
    # "bsm" = Black-Scholes-Merton, "mjd" = Merton Jump-Diffusion
    pricing_model: Literal["bsm", "mjd"] = "bsm"

    # Implied-vol proxy: rolling realized vol + volatility risk premium
    iv_window_days: int = 60
    iv_vrp: float = 0.03                  # +3% VRP added to realized vol
    iv_floor: float = 0.15
    iv_cap: float = 0.80

    # MJD params (annualized) — calibrated to QQQ-like large-cap equity index
    mjd_lambda: float = 1.2               # jumps per year
    mjd_jump_mean: float = -0.05          # mean log-jump size
    mjd_jump_std: float = 0.12            # std of log-jump size

    # ---- Market frictions ----
    commission_per_contract: float = 0.65
    slippage_bps: float = 25.0            # 25 bps on option price

    # ---- Misc ----
    contract_multiplier: int = 100
    dividend_yield: float = 0.005         # QQQ ~0.5%

    trend_filter: bool = True
    trend_sma_days: int = 200
