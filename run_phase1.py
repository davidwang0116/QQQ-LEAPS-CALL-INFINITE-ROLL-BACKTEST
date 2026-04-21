"""
Phase 1: Run 4 start-years × 2 pricing models.
Saves a pickle for phase 2/3 to load.
~3 minutes on typical hardware.
"""
import warnings, pickle, time
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
from config import StrategyConfig
from data import generate_synthetic_qqq, load_qqq_csv
from engine import BacktestEngine

CACHE = Path("_cache"); CACHE.mkdir(exist_ok=True)

def run_one(price_df, start_year, model, entry_delta=0.70,
            harvest_delta=0.90, initial_cash=100_000, end=None):
    cfg = StrategyConfig(pricing_model=model, entry_delta=entry_delta,
                         harvest_delta=harvest_delta)
    eng = BacktestEngine(price_df, cfg,
                         start=pd.Timestamp(f"{start_year}-01-04"),
                         end=end or price_df.index[-1],
                         initial_cash=initial_cash)
    return eng.run()

def main():
    csv = Path("QQQ.csv")
    if csv.exists():
        print(f"Loading real QQQ from {csv}")
        price_df = load_qqq_csv(csv)
    else:
        print("Using synthetic QQQ (calibrated to real historical anchors).")
        price_df = generate_synthetic_qqq()
    end_date = price_df.index[-1]
    print(f"Data: {price_df.index[0].date()} -> {end_date.date()}\n")

    results = {}
    for model in ("bsm", "mjd"):
        for sy in (2000, 2005, 2010, 2020):
            name = f"{sy}_{model.upper()}"
            t0 = time.time()
            res = run_one(price_df, sy, model, end=end_date)
            m = res.metrics()
            print(f"{name:10s} {time.time()-t0:5.1f}s  "
                  f"CAGR {m['cagr']*100:6.2f}%  QQQ {m['qqq_cagr']*100:6.2f}%  "
                  f"MaxDD {m['max_drawdown']*100:6.1f}%  Sharpe {m['sharpe']:.2f}")
            results[name] = res

    with open(CACHE / "phase1_results.pkl", "wb") as f:
        pickle.dump(results, f)
    print(f"\nSaved -> {CACHE}/phase1_results.pkl")

if __name__ == "__main__":
    main()
