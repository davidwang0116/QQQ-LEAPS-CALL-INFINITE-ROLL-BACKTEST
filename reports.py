"""
Reports and visualization for backtest results.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from engine import BacktestResults


# ---------------------------------------------------------------------------
# Metric table
# ---------------------------------------------------------------------------
def summary_table(results: dict[str, BacktestResults]) -> pd.DataFrame:
    """
    results: dict keyed by scenario name -> BacktestResults.
    Returns a tidy DataFrame of metrics per scenario.
    """
    rows = []
    for name, res in results.items():
        m = res.metrics()
        rows.append({
            "Scenario": name,
            "Years": round(m["years"], 2),
            "Strategy CAGR": f"{m['cagr']*100:.2f}%",
            "QQQ CAGR": f"{m['qqq_cagr']*100:.2f}%",
            "Strategy Total": f"{m['total_return']*100:.1f}%",
            "QQQ Total": f"{m['qqq_total_return']*100:.1f}%",
            "Strategy Vol": f"{m['vol']*100:.1f}%",
            "QQQ Vol": f"{m['qqq_vol']*100:.1f}%",
            "Sharpe": round(m["sharpe"], 2),
            "Max DD": f"{m['max_drawdown']*100:.1f}%",
            "QQQ Max DD": f"{m['qqq_max_drawdown']*100:.1f}%",
            "Final $": f"${m['final_value']:,.0f}",
            "Entries": m["n_entries"],
            "Snipes": m["n_snipes"],
            "Harvests": m["n_harvests"] // 2,        # each roll = 1 close + 1 open
            "Forced Rolls": m["n_forced_rolls"] // 2,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Per-scenario plot
# ---------------------------------------------------------------------------
def plot_scenario(res: BacktestResults, title: str,
                  save_path: Path | str) -> None:
    eq = res.equity
    initial = res.initial_cash

    fig, axes = plt.subplots(4, 1, figsize=(12, 11),
                             sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.3, 1, 1]})

    # --- (1) Equity curve vs QQQ buy-and-hold ---
    ax = axes[0]
    strat = eq["portfolio"]
    spot = eq["spot"]
    bh = spot / spot.iloc[0] * initial
    ax.plot(strat.index, strat.values, color="#d62728", lw=1.7,
            label="LEAPS strategy")
    ax.plot(bh.index, bh.values, color="#1f77b4", lw=1.3,
            label="QQQ buy-and-hold", alpha=0.8)
    ax.set_yscale("log")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Portfolio value ($, log)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3, which="both")

    # Mark entry events
    trades = res.trades
    if len(trades) > 0:
        entries = trades[trades["trigger"].isin(["entry", "snipe"]) & (trades["action"] == "open")]
        ax.scatter(entries["date"], [strat.asof(d) for d in entries["date"]],
                   c=entries["trigger"].map({"entry": "green", "snipe": "orange"}),
                   s=14, zorder=5, alpha=0.6, edgecolors="none",
                   label="_nolegend_")

    # --- (2) Drawdown ---
    ax = axes[1]
    dd_strat = strat / strat.cummax() - 1
    dd_bh = bh / bh.cummax() - 1
    ax.fill_between(dd_strat.index, dd_strat.values, 0,
                    color="#d62728", alpha=0.35, label="Strategy DD")
    ax.plot(dd_bh.index, dd_bh.values, color="#1f77b4",
            lw=1.0, alpha=0.8, label="QQQ DD")
    ax.set_ylabel("Drawdown")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x*100:.0f}%"))
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(alpha=0.3)

    # --- (3) Cash % ---
    ax = axes[2]
    ax.plot(eq.index, eq["cash_pct"].values * 100, color="#2ca02c", lw=1.1)
    ax.axhline(40, color="gray", ls="--", lw=0.7)
    ax.axhline(10, color="gray", ls="--", lw=0.7)
    ax.set_ylabel("Cash %")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.3)

    # --- (4) Number of active positions and average delta ---
    ax = axes[3]
    ax2 = ax.twinx()
    ax.plot(eq.index, eq["n_positions"].values, color="#9467bd",
            lw=1.0, label="# positions")
    ax2.plot(eq.index, eq["avg_delta"].values, color="#ff7f0e",
             lw=1.0, alpha=0.7, label="avg delta")
    ax.set_ylabel("# positions", color="#9467bd")
    ax2.set_ylabel("Avg delta", color="#ff7f0e")
    ax2.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.set_xlabel("Date")

    axes[-1].xaxis.set_major_locator(mdates.YearLocator(max(1, int((eq.index[-1]-eq.index[0]).days/365/6))))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    plt.savefig(save_path, dpi=110, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# Multi-scenario comparison panel
# ---------------------------------------------------------------------------
def plot_multi_comparison(results: dict[str, BacktestResults],
                          save_path: Path | str,
                          title: str = "QQQ LEAPS Strategy — Starting-Year Comparison") -> None:
    """2x2 grid comparing all scenarios."""
    n = len(results)
    ncols = 2
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4.2 * nrows),
                             sharex=False)
    axes = np.atleast_2d(axes).ravel()

    for ax, (name, res) in zip(axes, results.items()):
        eq = res.equity
        strat = eq["portfolio"]
        spot = eq["spot"]
        bh = spot / spot.iloc[0] * res.initial_cash
        ax.plot(strat.index, strat.values, color="#d62728", lw=1.7, label="LEAPS")
        ax.plot(bh.index, bh.values, color="#1f77b4", lw=1.2, label="QQQ B&H")
        ax.set_yscale("log")
        m = res.metrics()
        ax.set_title(
            f"{name}  |  Strat CAGR {m['cagr']*100:.1f}%  vs  QQQ {m['qqq_cagr']*100:.1f}%\n"
            f"Strat MaxDD {m['max_drawdown']*100:.0f}%  vs  QQQ {m['qqq_max_drawdown']*100:.0f}%",
            fontsize=10,
        )
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(alpha=0.3, which="both")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    for ax in axes[n:]:
        ax.axis("off")

    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.00)
    plt.tight_layout()
    plt.savefig(save_path, dpi=110, bbox_inches="tight")
    plt.close()


# ---------------------------------------------------------------------------
# Delta-sensitivity heatmap
# ---------------------------------------------------------------------------
def plot_delta_sensitivity(grid: pd.DataFrame, save_path: Path | str,
                           metric: str = "cagr",
                           title: str | None = None) -> None:
    """
    grid: long-format DataFrame with columns [entry_delta, harvest_delta, <metric>]
    Pivot into a heatmap.
    """
    pivot = grid.pivot(index="harvest_delta", columns="entry_delta",
                       values=metric)
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    im = ax.imshow(pivot.values, aspect="auto", origin="lower",
                   cmap="RdYlGn")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{v:.2f}" for v in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{v:.2f}" for v in pivot.index])
    ax.set_xlabel("Entry delta (target)")
    ax.set_ylabel("Harvest delta (threshold)")
    ax.set_title(title or f"Sensitivity: {metric}")
    # Annotate cells
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v*100:.1f}%" if metric in ("cagr","max_drawdown","total_return") else f"{v:.2f}",
                        ha="center", va="center", fontsize=9,
                        color="black" if abs(v) < 0.5 else "white")
    fig.colorbar(im, ax=ax, shrink=0.85)
    plt.tight_layout()
    plt.savefig(save_path, dpi=110, bbox_inches="tight")
    plt.close()
