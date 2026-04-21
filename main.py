"""
Main runner for the QQQ LEAPS Call strategy backtest.

Produces:
  - A summary CSV of metrics across 4 start years (2000/2005/2010/2020) x 2 pricing models
  - A multi-panel comparison plot
  - Per-scenario detail plots
  - A delta (entry,harvest) sensitivity heatmap for the 2010 BSM scenario
  - A full trade log for the 2020 BSM scenario
"""
from __future__ import annotations
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import numpy as np
import pandas as pd

from config import StrategyConfig
from data import generate_synthetic_qqq, load_qqq_csv
from engine import BacktestEngine
from reports import (
    summary_table,
    plot_scenario,
    plot_multi_comparison,
    plot_delta_sensitivity,
)

OUT = Path("/mnt/user-data/outputs")
OUT.mkdir(parents=True, exist_ok=True)


def run_one(price_df, start_year: int, pricing_model: str,
            entry_delta: float = 0.70, harvest_delta: float = 0.90,
            initial_cash: float = 100_000.0,
            end: pd.Timestamp | None = None):
    cfg = StrategyConfig(
        pricing_model=pricing_model,
        entry_delta=entry_delta,
        harvest_delta=harvest_delta,
    )
    start = pd.Timestamp(f"{start_year}-01-04")
    end = end or price_df.index[-1]
    eng = BacktestEngine(price_df, cfg, start=start, end=end,
                         initial_cash=initial_cash)
    return eng.run()


def main():
    # --- Load / generate price data -----------------------------------
    csv_path = Path("/mnt/user-data/uploads/QQQ.csv")
    if csv_path.exists():
        print(f"Loading real QQQ data from {csv_path}")
        price_df = load_qqq_csv(csv_path)
        data_note = f"real QQQ data ({csv_path.name})"
    else:
        print("Generating synthetic QQQ data (calibrated to real history).")
        price_df = generate_synthetic_qqq()
        data_note = "synthetic QQQ (calibrated to real anchors)"

    end_date = price_df.index[-1]
    print(f"Data range: {price_df.index[0].date()} -> {end_date.date()}  "
          f"({len(price_df)} rows)")
    print(f"Source: {data_note}\n")

    # --- (1) Main 4x2 grid: (start year) x (pricing model) -----------
    scenarios = {}
    start_years = [2000, 2005, 2010, 2020]
    for model in ("bsm", "mjd"):
        for sy in start_years:
            name = f"{sy}_{model.upper()}"
            print(f"Running {name} ...")
            res = run_one(price_df, sy, model, end=end_date)
            scenarios[name] = res
            m = res.metrics()
            print(f"    CAGR {m['cagr']*100:6.2f}%  | QQQ {m['qqq_cagr']*100:6.2f}%  "
                  f"| MaxDD {m['max_drawdown']*100:6.1f}%  "
                  f"| Sharpe {m['sharpe']:.2f}")

    # --- Summary table -----------------------------------------------
    table = summary_table(scenarios)
    summary_path = OUT / "qqq_leaps_summary.csv"
    table.to_csv(summary_path, index=False)
    print(f"\nSaved summary table -> {summary_path}")
    print("\n" + table.to_string(index=False))

    # --- Multi-scenario comparison plot for BSM ----------------------
    bsm_scenarios = {k: v for k, v in scenarios.items() if k.endswith("BSM")}
    plot_multi_comparison(
        bsm_scenarios,
        OUT / "qqq_leaps_scenarios_BSM.png",
        title="QQQ LEAPS Call Strategy — BSM Pricing — Start-Year Comparison",
    )

    mjd_scenarios = {k: v for k, v in scenarios.items() if k.endswith("MJD")}
    plot_multi_comparison(
        mjd_scenarios,
        OUT / "qqq_leaps_scenarios_MJD.png",
        title="QQQ LEAPS Call Strategy — MJD Pricing — Start-Year Comparison",
    )

    # --- Per-scenario detailed plots (BSM + MJD for 2010 and 2020) ---
    for key in ("2000_BSM", "2005_BSM", "2010_BSM", "2020_BSM", "2020_MJD"):
        res = scenarios[key]
        plot_scenario(
            res, title=f"QQQ LEAPS Strategy — {key}",
            save_path=OUT / f"qqq_leaps_detail_{key}.png",
        )

    # --- (2) Delta sensitivity sweep on 2010-start BSM ---------------
    print("\nRunning delta-sensitivity sweep (2010 start, BSM)...")
    entry_deltas = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    harvest_deltas = [0.80, 0.85, 0.90, 0.95]
    sens_rows = []
    for ed in entry_deltas:
        for hd in harvest_deltas:
            if hd <= ed:
                continue
            res = run_one(price_df, 2010, "bsm",
                          entry_delta=ed, harvest_delta=hd,
                          end=end_date)
            m = res.metrics()
            sens_rows.append({
                "entry_delta": ed,
                "harvest_delta": hd,
                "cagr": m["cagr"],
                "max_drawdown": m["max_drawdown"],
                "sharpe": m["sharpe"],
                "final_value": m["final_value"],
            })
    sens_df = pd.DataFrame(sens_rows)
    sens_df.to_csv(OUT / "qqq_leaps_delta_sensitivity.csv", index=False)
    plot_delta_sensitivity(
        sens_df, OUT / "qqq_leaps_delta_sensitivity_cagr.png",
        metric="cagr",
        title="CAGR sensitivity — 2010 start, BSM"
    )
    plot_delta_sensitivity(
        sens_df, OUT / "qqq_leaps_delta_sensitivity_maxdd.png",
        metric="max_drawdown",
        title="Max-drawdown sensitivity — 2010 start, BSM"
    )
    plot_delta_sensitivity(
        sens_df, OUT / "qqq_leaps_delta_sensitivity_sharpe.png",
        metric="sharpe",
        title="Sharpe sensitivity — 2010 start, BSM"
    )
    print("Best (entry, harvest) by CAGR:")
    print(sens_df.sort_values("cagr", ascending=False).head(3).to_string(index=False))

    # --- Trade log for 2020 BSM --------------------------------------
    scenarios["2020_BSM"].trades.to_csv(OUT / "qqq_leaps_trades_2020_BSM.csv", index=False)
    scenarios["2020_BSM"].equity.to_csv(OUT / "qqq_leaps_equity_2020_BSM.csv")

    # --- BSM vs MJD comparison ---------------------------------------
    rows = []
    for sy in start_years:
        bsm = scenarios[f"{sy}_BSM"].metrics()
        mjd = scenarios[f"{sy}_MJD"].metrics()
        rows.append({
            "Start Year": sy,
            "BSM CAGR": f"{bsm['cagr']*100:.2f}%",
            "MJD CAGR": f"{mjd['cagr']*100:.2f}%",
            "BSM MaxDD": f"{bsm['max_drawdown']*100:.1f}%",
            "MJD MaxDD": f"{mjd['max_drawdown']*100:.1f}%",
            "BSM Sharpe": f"{bsm['sharpe']:.2f}",
            "MJD Sharpe": f"{mjd['sharpe']:.2f}",
            "BSM Final $": f"${bsm['final_value']:,.0f}",
            "MJD Final $": f"${mjd['final_value']:,.0f}",
        })
    bsm_vs_mjd = pd.DataFrame(rows)
    bsm_vs_mjd.to_csv(OUT / "qqq_leaps_BSM_vs_MJD.csv", index=False)
    print("\n--- BSM vs MJD ---")
    print(bsm_vs_mjd.to_string(index=False))

    print("\nAll outputs written to", OUT)


if __name__ == "__main__":
    main()
