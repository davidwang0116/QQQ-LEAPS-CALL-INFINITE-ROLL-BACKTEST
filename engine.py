"""
Backtest engine for the QQQ LEAPS Call strategy.

Strategy rules (from user spec):

ENTRY
  - Triggered when today's Open <= yesterday's Close * (1 + gap_down_threshold)
    (default gap_down_threshold = -1%)
  - Sized by cash level:
      cash > 40%  -> deploy 10% of cash
      10% < cash <= 40% -> deploy 5% of cash
      cash <= 10% -> skip
  - Buy: latest quarterly expiration with DTE in [650, 800] at target delta
    (default 0.7)

HARVEST
  - When any held position's delta >= harvest_delta (default 0.9):
    roll it to a new 650-800 DTE, entry_delta LEAPS.

FORCED ROLL
  - When DTE <= 300 and harvest never triggered: spend cash to roll to a
    quarterly expiry with DTE >= 650 at entry_delta.

COUNTER-TREND SNIPE
  - If any held delta < 0.5 AND cash > 10% AND cooldown_days since last snipe:
    treat as entry trigger.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config import StrategyConfig
from data import risk_free_rate, realized_vol
from options import (
    OptionPosition,
    find_target_expiration,
    find_roll_target_expiration,
)
from pricing import OptionPricer


# ---------------------------------------------------------------------------
# Trade log entry
# ---------------------------------------------------------------------------
@dataclass
class TradeRecord:
    date: pd.Timestamp
    action: str                 # "open" | "close"
    trigger: str                # "entry" | "snipe" | "harvest_roll" | "forced_roll"
    contracts: int
    expiry: pd.Timestamp
    strike: float
    spot: float
    iv: float
    option_price: float
    cashflow: float             # debit negative, credit positive
    delta: float
    dte: int
    note: str = ""


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------
class BacktestEngine:
    def __init__(self,
                 price_df: pd.DataFrame,
                 cfg: StrategyConfig,
                 start: pd.Timestamp,
                 end: Optional[pd.Timestamp] = None,
                 initial_cash: float = 100_000.0):
        self.cfg = cfg
        self.prices = price_df.copy()
        self.start = pd.Timestamp(start)
        self.end = pd.Timestamp(end) if end is not None else price_df.index[-1]

        # Slice price data — keep some lookback for realized vol
        self._rv = realized_vol(self.prices["Close"], cfg.iv_window_days)
        self.prices = self.prices.loc[self.start - pd.Timedelta(days=200):self.end]

        # Pricer
        self.pricer = OptionPricer(
            model=cfg.pricing_model,
            lam=cfg.mjd_lambda, muJ=cfg.mjd_jump_mean, sigJ=cfg.mjd_jump_std,
        )

        # Precompute per-day IV and r arrays keyed by date for O(1) lookup
        self._iv_cache: dict[pd.Timestamp, float] = {}
        self._r_cache: dict[pd.Timestamp, float] = {}
        rv_series = self._rv.reindex(self.prices.index).ffill()
        default_iv = max(cfg.iv_floor, min(cfg.iv_cap, 0.25 + cfg.iv_vrp))
        for d, rv in rv_series.items():
            if pd.isna(rv):
                self._iv_cache[d] = default_iv
            else:
                iv = rv + cfg.iv_vrp
                self._iv_cache[d] = max(cfg.iv_floor, min(cfg.iv_cap, iv))
            self._r_cache[d] = risk_free_rate(d)

        # State
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.positions: list[OptionPosition] = []
        self.trades: list[TradeRecord] = []
        self.last_snipe_date: Optional[pd.Timestamp] = None

        # Equity curve rows
        self._equity_rows: list[dict] = []

    # -----------------------------------------------------------------
    # IV proxy — O(1) lookup from precomputed dict
    # -----------------------------------------------------------------
    def _iv_for(self, date: pd.Timestamp) -> float:
        iv = self._iv_cache.get(date)
        if iv is None:
            # Fallback for dates outside the window
            rv = self._rv.asof(date)
            if pd.isna(rv):
                rv = 0.25
            iv = max(self.cfg.iv_floor, min(self.cfg.iv_cap, rv + self.cfg.iv_vrp))
        return iv

    def _r_for(self, date: pd.Timestamp) -> float:
        r = self._r_cache.get(date)
        if r is None:
            r = risk_free_rate(date)
        return r

    # -----------------------------------------------------------------
    # Utility: mark one position
    # -----------------------------------------------------------------
    def _mark_position(self, pos: OptionPosition, spot: float,
                       date: pd.Timestamp) -> None:
        T = max((pos.expiry - date).days / 365.25, 1e-6)
        r = self._r_for(date)
        iv = self._iv_for(date)
        price, delta = self.pricer.price_and_delta(
            spot, pos.strike, T, r, self.cfg.dividend_yield, iv, "call"
        )
        pos.current_price = price
        pos.current_delta = delta

    def _mark_all(self, spot: float, date: pd.Timestamp) -> None:
        for p in self.positions:
            self._mark_position(p, spot, date)

    def portfolio_value(self) -> float:
        return self.cash + sum(p.market_value() for p in self.positions)

    def options_value(self) -> float:
        return sum(p.market_value() for p in self.positions)

    def cash_pct(self) -> float:
        pv = self.portfolio_value()
        return self.cash / pv if pv > 0 else 1.0

    # -----------------------------------------------------------------
    # Option pricing with frictions
    # -----------------------------------------------------------------
    def _apply_slippage(self, mid_price: float, side: str) -> float:
        """side='buy' -> pay higher, side='sell' -> receive lower."""
        bps = self.cfg.slippage_bps / 10_000.0
        return mid_price * (1 + bps) if side == "buy" else mid_price * (1 - bps)

    # -----------------------------------------------------------------
    # Buying an entry-delta LEAPS
    # -----------------------------------------------------------------
    def _build_new_leaps(self, spot: float, date: pd.Timestamp,
                         target_delta: float,
                         expiry: pd.Timestamp) -> tuple[float, float, float]:
        """
        Return (strike, mid_price, iv) for a new LEAPS with the specified
        target delta and expiration.
        """
        T = max((expiry - date).days / 365.25, 1e-6)
        r = self._r_for(date)
        iv = self._iv_for(date)
        K = self.pricer.strike_from_delta(
            spot, T, r, self.cfg.dividend_yield, iv, target_delta, "call"
        )
        price = self.pricer.price(
            spot, K, T, r, self.cfg.dividend_yield, iv, "call"
        )
        return K, price, iv

    def _contracts_affordable(self, budget: float, mid_price: float) -> int:
        """Maximum whole contracts that fit in budget, accounting for
        slippage and commission."""
        ask = self._apply_slippage(mid_price, "buy")
        # each contract costs ask * 100 + commission
        per_ct = ask * 100 + self.cfg.commission_per_contract
        if per_ct <= 0:
            return 0
        return int(budget // per_ct)

    def _buy_leaps(self, spot: float, date: pd.Timestamp,
                   budget: float, trigger: str,
                   target_delta: Optional[float] = None) -> Optional[OptionPosition]:
        """Open a new LEAPS position given a cash budget."""
        target_delta = target_delta if target_delta is not None else self.cfg.entry_delta
        expiry = find_target_expiration(date, self.cfg.dte_min, self.cfg.dte_max)
        if expiry is None:
            return None
        K, mid, iv = self._build_new_leaps(spot, date, target_delta, expiry)
        n_ct = self._contracts_affordable(budget, mid)
        if n_ct <= 0:
            return None
        ask = self._apply_slippage(mid, "buy")
        total_cost = ask * 100 * n_ct + self.cfg.commission_per_contract * n_ct
        if total_cost > self.cash + 1e-6:
            return None  # safety
        self.cash -= total_cost

        pos = OptionPosition(
            entry_date=date,
            expiry=expiry,
            strike=K,
            contracts=n_ct,
            entry_spot=spot,
            entry_iv=iv,
            entry_price=ask,
            entry_cost=total_cost,
            trigger=trigger,
        )
        pos.current_price = mid
        pos.current_delta = self.pricer.delta(
            spot, K, max((expiry-date).days/365.25, 1e-6),
            self._r_for(date), self.cfg.dividend_yield, iv, "call"
        )
        self.positions.append(pos)

        self.trades.append(TradeRecord(
            date=date, action="open", trigger=trigger,
            contracts=n_ct, expiry=expiry, strike=K,
            spot=spot, iv=iv, option_price=ask,
            cashflow=-total_cost,
            delta=pos.current_delta,
            dte=(expiry - date).days,
            note=f"budget={budget:.0f}",
        ))
        return pos

    # -----------------------------------------------------------------
    # Sell a position
    # -----------------------------------------------------------------
    def _sell_position(self, pos: OptionPosition, spot: float,
                       date: pd.Timestamp, trigger: str,
                       note: str = "") -> float:
        """Close position at current mid, return net proceeds."""
        self._mark_position(pos, spot, date)
        bid = self._apply_slippage(pos.current_price, "sell")
        proceeds = bid * 100 * pos.contracts - self.cfg.commission_per_contract * pos.contracts
        self.cash += proceeds
        self.positions.remove(pos)

        self.trades.append(TradeRecord(
            date=date, action="close", trigger=trigger,
            contracts=pos.contracts, expiry=pos.expiry, strike=pos.strike,
            spot=spot, iv=self._iv_for(date), option_price=bid,
            cashflow=proceeds,
            delta=pos.current_delta,
            dte=(pos.expiry - date).days,
            note=note,
        ))
        return proceeds

    # -----------------------------------------------------------------
    # Roll a position (sell old, buy new at entry_delta)
    # -----------------------------------------------------------------
    def _roll_position(self, pos: OptionPosition, spot: float,
                       date: pd.Timestamp, trigger: str) -> None:
        old_contracts = pos.contracts

        if trigger == "forced_roll":
            expiry = find_roll_target_expiration(date, self.cfg.forced_roll_target_dte)
        else:
            expiry = find_target_expiration(date, self.cfg.dte_min, self.cfg.dte_max)
            if expiry is None:
                expiry = find_roll_target_expiration(date, self.cfg.forced_roll_target_dte)

        K, mid, iv = self._build_new_leaps(
            spot, date, self.cfg.entry_delta, expiry
        )

        ask = self._apply_slippage(mid, "buy")
        per_ct = ask * 100 + self.cfg.commission_per_contract

        # ── Check affordability BEFORE touching the old position ────────────
        # proceeds from selling the old position count toward the budget
        # (we estimate them as current market value minus slippage/commission)
        bid = self._apply_slippage(pos.current_price, "sell")
        estimated_proceeds = bid * 100 * old_contracts - self.cfg.commission_per_contract * old_contracts
        available = self.cash + estimated_proceeds

        n_ct = old_contracts if per_ct * old_contracts <= available + 1e-6 else int(available // per_ct)

        if n_ct <= 0:
            # Can't afford even 1 new contract — leave position as-is, do nothing
            return

        # ── Now safe to sell old and open new ───────────────────────────────
        proceeds = self._sell_position(pos, spot, date, trigger,
                                       note=f"roll_{trigger}")

        total_cost = per_ct * n_ct
        self.cash -= total_cost

        new_pos = OptionPosition(
            entry_date=date,
            expiry=expiry,
            strike=K,
            contracts=n_ct,
            entry_spot=spot,
            entry_iv=iv,
            entry_price=ask,
            entry_cost=total_cost,
            trigger=trigger,
        )
        new_pos.current_price = mid
        new_pos.current_delta = self.pricer.delta(
            spot, K, max((expiry-date).days/365.25, 1e-6),
            self._r_for(date), self.cfg.dividend_yield, iv, "call"
        )
        self.positions.append(new_pos)

        self.trades.append(TradeRecord(
            date=date, action="open", trigger=trigger,
            contracts=n_ct, expiry=expiry, strike=K,
            spot=spot, iv=iv, option_price=ask,
            cashflow=-total_cost,
            delta=new_pos.current_delta,
            dte=(expiry - date).days,
            note=f"replaces old {old_contracts} contracts, proceeds={proceeds:.0f}",
        ))

    # -----------------------------------------------------------------
    # Entry-rule execution
    # -----------------------------------------------------------------
    def _execute_entry_rule(self, spot: float, date: pd.Timestamp,
                            trigger: str) -> bool:
        cash_frac = self.cash_pct()
        if cash_frac > self.cfg.cash_tier_high:
            budget = self.cash * self.cfg.size_high
        elif cash_frac > self.cfg.cash_tier_low:
            budget = self.cash * self.cfg.size_mid
        else:
            return False
        pos = self._buy_leaps(spot, date, budget, trigger)
        return pos is not None

    # -----------------------------------------------------------------
    # One-day step
    # -----------------------------------------------------------------
    def _step(self, date: pd.Timestamp,
              open_px: float, close_px: float,
              prev_close: float) -> None:
        # --- 1) Check gap-down entry at OPEN ---
        entry_took_place = False
        if prev_close > 0:
            gap = open_px / prev_close - 1.0
            if gap <= self.cfg.gap_down_threshold:
                self._mark_all(open_px, date)  # mark at open so cash_pct is fresh
                entry_took_place = self._execute_entry_rule(open_px, date, "entry")

        # --- 2) Intraday: positions move. Re-mark at CLOSE. ---
        self._mark_all(close_px, date)

        # --- 3) Harvest: positions with delta >= harvest threshold ---
        # Snapshot IDs first; re-check membership before each roll
        harvest_ids = {id(p) for p in self.positions
                       if p.current_delta >= self.cfg.harvest_delta}
        for p in list(self.positions):
            if id(p) in harvest_ids and p in self.positions:
                self._roll_position(p, close_px, date, "harvest_roll")

        # --- 4) Forced roll: DTE <= 300 ---
        # Skip positions that can't be rolled (cash too low) rather than
        # selling them and leaving an orphaned close.
        force_ids = {id(p) for p in self.positions
                     if (p.expiry - date).days <= self.cfg.forced_roll_dte}
        for p in list(self.positions):
            if id(p) in force_ids and p in self.positions:
                self._roll_position(p, close_px, date, "forced_roll")

        # --- 5) Counter-trend snipe ---
        if not entry_took_place:
            any_low_delta = any(p.current_delta < self.cfg.snipe_delta
                                for p in self.positions)
            cash_ok = self.cash_pct() > self.cfg.snipe_cash_min
            cooldown_ok = (
                self.last_snipe_date is None
                or (date - self.last_snipe_date).days >= self.cfg.snipe_cooldown_days
            )
            if any_low_delta and cash_ok and cooldown_ok:
                success = self._execute_entry_rule(close_px, date, "snipe")
                if success:
                    self.last_snipe_date = date

        # --- 6) Record equity (re-mark after all rolls/entries) ---
        self._mark_all(close_px, date)
        self._equity_rows.append({
            "date": date,
            "spot": close_px,
            "cash": self.cash,
            "options_mv": self.options_value(),
            "portfolio": self.portfolio_value(),
            "n_positions": len(self.positions),
            "cash_pct": self.cash_pct(),
            "avg_delta": (float(np.mean([p.current_delta for p in self.positions]))
                          if self.positions else 0.0),
        })

    # -----------------------------------------------------------------
    # Main run loop
    # -----------------------------------------------------------------
    def run(self) -> "BacktestResults":
        prices = self.prices.loc[self.start:self.end]
        if len(prices) == 0:
            raise ValueError("No price data in the specified window.")

        # Previous close before the first day of the window
        # (for the gap-down calculation on day 1)
        try:
            first_idx = self.prices.index.get_loc(prices.index[0])
            prev_close = (self.prices["Close"].iloc[first_idx - 1]
                          if first_idx > 0 else prices["Open"].iloc[0])
        except Exception:
            prev_close = prices["Open"].iloc[0]

        for date, row in prices.iterrows():
            self._step(date, row["Open"], row["Close"], prev_close)
            prev_close = row["Close"]

        # Close out remaining positions at end for clean P&L
        final_date = prices.index[-1]
        final_px = prices["Close"].iloc[-1]
        for p in list(self.positions):
            self._sell_position(p, final_px, final_date, "final_close",
                                note="end_of_backtest")

        return BacktestResults(
            config=self.cfg,
            equity=pd.DataFrame(self._equity_rows).set_index("date"),
            trades=pd.DataFrame([t.__dict__ for t in self.trades]),
            prices=prices,
            initial_cash=self.initial_cash,
        )


# ---------------------------------------------------------------------------
# Results container with metrics
# ---------------------------------------------------------------------------
@dataclass
class BacktestResults:
    config: StrategyConfig
    equity: pd.DataFrame
    trades: pd.DataFrame
    prices: pd.DataFrame
    initial_cash: float

    def metrics(self) -> dict:
        eq = self.equity["portfolio"]
        if len(eq) < 2:
            return {}
        total_ret = eq.iloc[-1] / eq.iloc[0] - 1
        years = (eq.index[-1] - eq.index[0]).days / 365.25
        cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / max(years, 1e-6)) - 1
        daily_ret = eq.pct_change().dropna()
        vol = daily_ret.std() * np.sqrt(252)
        sharpe = (daily_ret.mean() * 252) / vol if vol > 0 else 0.0
        rolling_max = eq.cummax()
        drawdown = eq / rolling_max - 1
        max_dd = drawdown.min()

        # Benchmark: QQQ buy-and-hold
        spot = self.equity["spot"]
        bh_ret = spot.iloc[-1] / spot.iloc[0] - 1
        bh_cagr = (spot.iloc[-1] / spot.iloc[0]) ** (1.0 / max(years, 1e-6)) - 1
        bh_dd = (spot / spot.cummax() - 1).min()
        bh_vol = np.log(spot / spot.shift(1)).std() * np.sqrt(252)

        return {
            "years": years,
            "total_return": total_ret,
            "cagr": cagr,
            "vol": vol,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "final_value": eq.iloc[-1],
            "qqq_total_return": bh_ret,
            "qqq_cagr": bh_cagr,
            "qqq_max_drawdown": bh_dd,
            "qqq_vol": bh_vol,
            "n_trades": len(self.trades),
            "n_opens": int((self.trades["action"] == "open").sum()),
            "n_closes": int((self.trades["action"] == "close").sum()),
            "n_entries": int((self.trades["trigger"] == "entry").sum()),
            "n_snipes": int((self.trades["trigger"] == "snipe").sum()),
            "n_harvests": int((self.trades["trigger"] == "harvest_roll").sum()),
            "n_forced_rolls": int((self.trades["trigger"] == "forced_roll").sum()),
        }