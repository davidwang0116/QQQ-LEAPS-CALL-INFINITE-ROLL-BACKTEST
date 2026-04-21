"""
Option contract objects and the quarterly-expiration finder.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Quarterly expiration finder
# ---------------------------------------------------------------------------
def third_friday(year: int, month: int) -> pd.Timestamp:
    """Return the 3rd Friday of the given year/month."""
    d = pd.Timestamp(year=year, month=month, day=1)
    # weekday Friday == 4
    offset = (4 - d.weekday()) % 7
    first_friday = d + pd.Timedelta(days=offset)
    return first_friday + pd.Timedelta(days=14)


def quarterly_expirations(center_date: pd.Timestamp,
                          lookback_years: int = 0,
                          lookforward_years: int = 4) -> list[pd.Timestamp]:
    """
    List 3rd-Friday quarterly expirations (Mar/Jun/Sep/Dec) in the window
    [center - lookback_years, center + lookforward_years].
    """
    out = []
    y0 = center_date.year - lookback_years
    y1 = center_date.year + lookforward_years
    for y in range(y0, y1 + 1):
        for m in (3, 6, 9, 12):
            out.append(third_friday(y, m))
    return sorted(out)


def find_target_expiration(today: pd.Timestamp,
                           dte_min: int,
                           dte_max: int) -> Optional[pd.Timestamp]:
    """
    Return the LATEST quarterly expiration whose DTE is in [dte_min, dte_max].

    Interpretation of the spec:
      "使用该区间内最晚的已经开始交易的季度期权"
      = "use the latest quarterly option that has already started trading,
         within the 650–800d window"

    For LEAPS, CBOE lists contracts ~2.5y out, so anything with DTE <= 800
    can be assumed tradeable.
    """
    candidates = quarterly_expirations(today)
    valid = [e for e in candidates
             if dte_min <= (e - today).days <= dte_max]
    if not valid:
        return None
    return valid[-1]  # latest


def find_roll_target_expiration(today: pd.Timestamp,
                                min_dte: int = 650) -> pd.Timestamp:
    """
    For the forced-roll case: find a quarterly expiration with DTE >= min_dte.
    Use the nearest one meeting the threshold (shortest valid LEAPS).
    """
    candidates = quarterly_expirations(today)
    valid = [e for e in candidates if (e - today).days >= min_dte]
    return valid[0]


# ---------------------------------------------------------------------------
# Option position
# ---------------------------------------------------------------------------
@dataclass
class OptionPosition:
    """A single long-call LEAPS position."""
    entry_date: pd.Timestamp
    expiry: pd.Timestamp
    strike: float
    contracts: int              # number of contracts (100 shares each)
    entry_spot: float
    entry_iv: float
    entry_price: float          # premium per share at entry (not per contract)
    entry_cost: float           # total debit paid (incl. commissions & slippage)
    trigger: str                # "entry" | "snipe" | "harvest_roll" | "forced_roll"

    # Running state
    current_price: float = 0.0
    current_delta: float = 0.0

    def dte(self, today: pd.Timestamp) -> int:
        return (self.expiry - today).days

    def notional(self, spot: float) -> float:
        """Underlying-equivalent exposure = contracts * 100 * spot * delta."""
        return self.contracts * 100 * spot * self.current_delta

    def market_value(self) -> float:
        """Current mark-to-market value of the position."""
        return self.contracts * 100 * self.current_price
