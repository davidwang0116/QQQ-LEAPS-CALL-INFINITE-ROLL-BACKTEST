"""
QQQ price data.

PRIMARY PATH: load a real CSV with columns [Date, Open, High, Low, Close, Adj Close]
              via load_qqq_csv(path). This is what a user would do in production.

FALLBACK: generate_synthetic_qqq() produces a deterministic, QQQ-LIKE daily
          OHLC series from 1999-01-04 through 2026-04-20, calibrated to match
          the major regime transitions and drawdowns of real QQQ history:
            - Dot-com bubble/crash (2000-2002)
            - Recovery (2003-2007)
            - Financial crisis (2008)
            - Bull market (2009-2019)
            - COVID crash (2020)
            - Post-COVID rally + 2022 bear + 2023-2025 recovery
          Results on synthetic data are DEMONSTRATIVE, not predictive.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Regime definition — (start, end, annualized_drift, annualized_vol)
# Calibrated from memory of actual QQQ behavior; designed to produce a
# price path that hits real QQQ level anchors within ~10% at key dates.
# ---------------------------------------------------------------------------
_REGIMES = [
    # start_date,   end_date,      mu,      sigma    label
    ("1999-01-04", "2000-03-10",  0.55,   0.38,  "bubble_topping"),
    ("2000-03-11", "2002-10-09", -0.75,   0.48,  "dotcom_crash"),
    ("2002-10-10", "2007-10-31",  0.23,   0.22,  "recovery_2000s"),
    ("2007-11-01", "2008-11-20", -0.80,   0.45,  "gfc_crash"),
    ("2008-11-21", "2009-03-09", -0.40,   0.55,  "gfc_final_low"),
    ("2009-03-10", "2015-12-31",  0.22,   0.18,  "qe_bull"),
    ("2016-01-01", "2018-01-26",  0.25,   0.15,  "trump_rally"),
    ("2018-01-27", "2018-12-24", -0.25,   0.25,  "2018_correction"),
    ("2018-12-25", "2020-02-19",  0.38,   0.18,  "late_cycle"),
    ("2020-02-20", "2020-03-23", -3.20,   0.75,  "covid_crash"),
    ("2020-03-24", "2021-11-19",  0.72,   0.25,  "covid_rally"),
    ("2021-11-20", "2022-10-13", -0.55,   0.32,  "2022_bear"),
    ("2022-10-14", "2024-06-30",  0.42,   0.20,  "ai_rally"),
    ("2024-07-01", "2026-04-20",  0.18,   0.22,  "2025_onward"),
]

# Discrete jumps at well-known stress dates (log-return shock applied on that day)
_DISCRETE_JUMPS = {
    "2000-04-14": -0.10,
    "2001-09-17": -0.07,
    "2008-09-29": -0.09,
    "2008-10-15": -0.08,
    "2011-08-08": -0.06,
    "2018-02-05": -0.04,
    "2020-03-09": -0.08,
    "2020-03-12": -0.10,
    "2020-03-16": -0.12,
    "2022-01-24": -0.04,
    "2022-05-05": -0.05,
}

# Anchor levels used to rescale the generated path (approximate real QQQ closes).
# The generator solves for a multiplicative correction so that the path matches
# each anchor exactly.
_ANCHORS = {
    "1999-01-04": 51.0,
    "2000-03-10": 120.0,
    "2002-10-09": 20.0,
    "2007-10-31": 55.0,
    "2009-03-09": 27.0,
    "2015-12-31": 112.0,
    "2020-02-19": 237.0,
    "2020-03-23": 165.0,
    "2021-11-19": 408.0,
    "2022-10-13": 260.0,
    "2024-12-31": 530.0,
    "2026-04-20": 520.0,
}


def _business_days(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start=start, end=end)


def generate_synthetic_qqq(seed: int = 7) -> pd.DataFrame:
    """
    Return a daily OHLC DataFrame indexed by business day.
    Columns: Open, High, Low, Close.
    """
    rng = np.random.default_rng(seed)
    dates = _business_days(_REGIMES[0][0], _REGIMES[-1][1])
    n = len(dates)
    log_ret = np.zeros(n)

    # Build per-day drift/vol from regimes
    date_to_pos = {d: i for i, d in enumerate(dates)}
    trading_days_per_year = 252

    for start_s, end_s, mu, sigma, _label in _REGIMES:
        start = pd.Timestamp(start_s)
        end = pd.Timestamp(end_s)
        mask = (dates >= start) & (dates <= end)
        n_seg = mask.sum()
        if n_seg == 0:
            continue
        daily_mu = mu / trading_days_per_year
        daily_sigma = sigma / np.sqrt(trading_days_per_year)
        shocks = rng.normal(daily_mu - 0.5 * daily_sigma ** 2,
                            daily_sigma, size=n_seg)
        log_ret[mask] = shocks

    # Apply discrete jumps
    for date_s, shock in _DISCRETE_JUMPS.items():
        t = pd.Timestamp(date_s)
        if t in date_to_pos:
            log_ret[date_to_pos[t]] += shock

    # Base close series
    close = 100.0 * np.exp(np.cumsum(log_ret))
    close_s = pd.Series(close, index=dates)

    # Piecewise-linear rescaling through anchors so the synthetic path
    # hits each known historical level exactly.
    anchor_items = [(pd.Timestamp(k), v) for k, v in _ANCHORS.items()]
    anchor_items.sort()

    # Build scale factor that's a piecewise-linear interpolation (in log-space)
    # of the ratio anchor_level / close_at_anchor.
    anchor_dates = [d for d, _ in anchor_items]
    anchor_logratios = np.array(
        [np.log(v / close_s.asof(d)) for d, v in anchor_items]
    )

    # Interpolate in "day index" space
    anchor_x = np.array([dates.get_indexer([d])[0] for d in anchor_dates])
    all_x = np.arange(n)
    log_scale = np.interp(all_x, anchor_x, anchor_logratios)
    close = close_s.values * np.exp(log_scale)

    # Build OHLC — Open as previous-close * small overnight gap,
    # High/Low as intraday band.
    rng2 = np.random.default_rng(seed + 1)
    overnight_sigma = 0.008  # 0.8% overnight noise
    intraday_sigma = 0.010

    open_ = np.zeros(n)
    high = np.zeros(n)
    low = np.zeros(n)
    prev_close = close[0]
    for i in range(n):
        gap = rng2.normal(0, overnight_sigma)
        open_[i] = prev_close * np.exp(gap)
        band = abs(rng2.normal(0, intraday_sigma)) + 0.003
        hi_candidate = max(open_[i], close[i]) * (1 + band)
        lo_candidate = min(open_[i], close[i]) * (1 - band)
        high[i] = hi_candidate
        low[i] = lo_candidate
        prev_close = close[i]

    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
    }, index=dates)
    df.index.name = "Date"
    return df


def load_qqq_csv(path: str | Path) -> pd.DataFrame:
    """
    Load QQQ price history from a Yahoo-style CSV.
    Expected columns: Date, Open, High, Low, Close, Adj Close  (Volume optional).
    Uses Adj Close to back-adjust Open/High/Low if available.
    """
    df = pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = pd.DatetimeIndex(df.index)

    if "Adj Close" in df.columns and "Close" in df.columns:
        adj_factor = df["Adj Close"] / df["Close"]
        for col in ("Open", "High", "Low"):
            if col in df.columns:
                df[col] = df[col] * adj_factor
        df["Close"] = df["Adj Close"]

    keep = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
    return df[keep].astype(float)


# ---------------------------------------------------------------------------
# Time-varying risk-free rate
# ---------------------------------------------------------------------------
# Approximate US 2Y yield history (%) — used as the r input for LEAPS pricing.
_RATE_PIECES = [
    ("1999-01-01", 0.047),
    ("2000-01-01", 0.062),
    ("2001-01-01", 0.050),
    ("2002-01-01", 0.030),
    ("2003-01-01", 0.017),
    ("2004-01-01", 0.020),
    ("2005-01-01", 0.037),
    ("2006-01-01", 0.047),
    ("2007-01-01", 0.046),
    ("2008-01-01", 0.022),
    ("2009-01-01", 0.009),
    ("2010-01-01", 0.010),
    ("2011-01-01", 0.006),
    ("2012-01-01", 0.003),
    ("2013-01-01", 0.003),
    ("2014-01-01", 0.005),
    ("2015-01-01", 0.008),
    ("2016-01-01", 0.010),
    ("2017-01-01", 0.019),
    ("2018-01-01", 0.026),
    ("2019-01-01", 0.023),
    ("2020-01-01", 0.015),
    ("2020-04-01", 0.002),
    ("2021-01-01", 0.002),
    ("2022-01-01", 0.015),
    ("2022-07-01", 0.030),
    ("2023-01-01", 0.044),
    ("2024-01-01", 0.045),
    ("2025-01-01", 0.042),
    ("2026-01-01", 0.040),
]


def risk_free_rate(date: pd.Timestamp) -> float:
    """Return the approximate USD short rate for a given date."""
    r = _RATE_PIECES[0][1]
    for d, rate in _RATE_PIECES:
        if pd.Timestamp(d) <= date:
            r = rate
        else:
            break
    return r


def realized_vol(close: pd.Series, window: int = 60) -> pd.Series:
    """Annualized rolling realized volatility from log returns."""
    logret = np.log(close / close.shift(1))
    return logret.rolling(window).std() * np.sqrt(252)
