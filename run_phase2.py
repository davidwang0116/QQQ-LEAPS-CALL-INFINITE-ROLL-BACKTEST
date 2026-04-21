"""
Phase 2: Load phase-1 results and generate all plots + CSVs.
Run after run_phase1.py.
"""
import warnings, pickle
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
from reports import summary_table, plot_scenario, plot_multi_comparison

CACHE = Path("_cache")
OUT = Path("results")  # write outputs to results directory

def main():
    with open(CACHE / "phase1_results.pkl", "rb") as f:
        scenarios = pickle.load(f)

    # Summary tables
    table = summary_table(scenarios)
    table.to_csv(OUT / "qqq_leaps_summary.csv", index=False)
    print("=== Summary ===\n" + table.to_string(index=False) + "\n")

    rows = []
    for sy in (2000, 2005, 2010, 2020):
        b, m = scenarios[f"{sy}_BSM"].metrics(), scenarios[f"{sy}_MJD"].metrics()
        rows.append({"Start": sy,
            "BSM CAGR": f"{b['cagr']*100:.2f}%", "MJD CAGR": f"{m['cagr']*100:.2f}%",
            "BSM MaxDD": f"{b['max_drawdown']*100:.1f}%", "MJD MaxDD": f"{m['max_drawdown']*100:.1f}%",
            "BSM Sharpe": f"{b['sharpe']:.2f}", "MJD Sharpe": f"{m['sharpe']:.2f}",
            "QQQ CAGR": f"{b['qqq_cagr']*100:.2f}%",
            "BSM Final": f"${b['final_value']:,.0f}", "MJD Final": f"${m['final_value']:,.0f}"})
    pd.DataFrame(rows).to_csv(OUT / "qqq_leaps_BSM_vs_MJD.csv", index=False)

    # Comparison grids
    bsm = {k: v for k, v in scenarios.items() if k.endswith("BSM")}
    mjd = {k: v for k, v in scenarios.items() if k.endswith("MJD")}
    plot_multi_comparison(bsm, OUT / "qqq_leaps_scenarios_BSM.png",
                          title="QQQ LEAPS Strategy — BSM — Start-Year Comparison")
    plot_multi_comparison(mjd, OUT / "qqq_leaps_scenarios_MJD.png",
                          title="QQQ LEAPS Strategy — MJD — Start-Year Comparison")

    # Per-scenario detail plots
    for key in ("2000_BSM","2005_BSM","2010_BSM","2020_BSM","2020_MJD"):
        plot_scenario(scenarios[key], title=f"QQQ LEAPS Strategy — {key}",
                      save_path=OUT / f"qqq_leaps_detail_{key}.png")
        print(f"  detail: {key}")

    # Trade log + equity for 2020 BSM
    scenarios["2020_BSM"].trades.to_csv(OUT / "qqq_leaps_trades_2020_BSM.csv", index=False)
    scenarios["2020_BSM"].equity.to_csv(OUT / "qqq_leaps_equity_2020_BSM.csv")
    print("\nPhase 2 complete — all plots and CSVs written.")

if __name__ == "__main__":
    main()
