"""
Phase 3: Delta sensitivity sweep.
- 2020 start: full 6×5 grid  (~30s BSM)
- 2010 start: coarse 3×2 grid (~60s BSM)
Generates heatmaps for CAGR, MaxDD, Sharpe.
"""
import warnings, time
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
from config import StrategyConfig
from data import generate_synthetic_qqq, load_qqq_csv
from engine import BacktestEngine
from reports import plot_delta_sensitivity

OUT = Path("results")  # write outputs to results directory

def sweep(price_df, start_year, entry_deltas, harvest_deltas, end=None):
    rows = []
    for ed in entry_deltas:
        for hd in harvest_deltas:
            if hd <= ed + 0.05:
                continue
            cfg = StrategyConfig(pricing_model="bsm",
                                 entry_delta=ed, harvest_delta=hd)
            eng = BacktestEngine(price_df, cfg,
                                 start=pd.Timestamp(f"{start_year}-01-04"),
                                 end=end or price_df.index[-1])
            m = eng.run().metrics()
            rows.append({"entry_delta": ed, "harvest_delta": hd,
                         "cagr": m["cagr"], "max_drawdown": m["max_drawdown"],
                         "sharpe": m["sharpe"], "final_value": m["final_value"]})
    return pd.DataFrame(rows)

def main():
    csv = Path("QQQ.csv")
    price_df = load_qqq_csv(csv) if csv.exists() else generate_synthetic_qqq()
    end_date = price_df.index[-1]

    sweeps = [
        (2020, [0.55,0.60,0.65,0.70,0.75,0.80], [0.75,0.80,0.85,0.90,0.95]),
        (2010, [0.60,0.70,0.80],                [0.80,0.90]),
    ]
    for sy, eds, hds in sweeps:
        t0 = time.time()
        print(f"Sweeping {sy} ({len(eds)}×{len(hds)} grid)...")
        df = sweep(price_df, sy, eds, hds, end=end_date)
        df.to_csv(OUT / f"qqq_leaps_delta_sensitivity_{sy}.csv", index=False)
        print(f"  {time.time()-t0:.0f}s, {len(df)} points")
        print("  Top 3 CAGR:\n" +
              df.nlargest(3,"cagr")[["entry_delta","harvest_delta","cagr","max_drawdown","sharpe"]].to_string(index=False))
        print()
        for metric in ("cagr","max_drawdown","sharpe"):
            plot_delta_sensitivity(df, OUT / f"qqq_leaps_delta_sens_{sy}_{metric}.png",
                                   metric=metric, title=f"{metric} sensitivity — {sy} start")

    print("Phase 3 complete.")

if __name__ == "__main__":
    main()
