"""Export the results the dashboard shows into small JSON files (web/public/data/).

Only findings and the series needed to draw them are exported. Headline numbers are computed from the report
files, never typed in. Each file carries a `meta` block: source, period, and whether the data is real or simulated.

Run after the research scripts: python -m gasbook.export_dashboard
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from gasbook.config import DATA_RAW, DATA_REFERENCE, ROOT
from gasbook.research import var_backtest

REPORTS = ROOT / "reports"
OUT = ROOT / "web" / "public" / "data"


def clean(value, digits: int = 4):
    """JSON-safe scalar: round floats, NaN/inf -> None, timestamps -> ISO date strings."""
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        v = float(value)
        return None if math.isnan(v) or math.isinf(v) else round(v, digits)
    return value


def records(df: pd.DataFrame, digits: int = 4) -> list[dict]:
    return [{k: clean(v, digits) for k, v in row.items()} for row in df.to_dict(orient="records")]


def columns(df: pd.DataFrame, digits: int = 4) -> dict:
    """Column-oriented export (smaller for long series): {"date": [...], "value": [...]}."""
    return {c: [clean(v, digits) for v in df[c].tolist()] for c in df.columns}


def meta(title: str, source: str, period: str, simulated: bool, notes: str = "") -> dict:
    return {"title": title, "source": source, "period": period, "simulated": simulated, "notes": notes}


def read(name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(REPORTS / name, **kwargs)


def export_prices() -> dict:
    hh = pd.read_csv(DATA_RAW / "henry_hub_daily.csv", parse_dates=["date"])
    spikes = read("storm_watch_spikes.csv", parse_dates=["start", "end", "peak_day"])
    top = hh.nlargest(1, "henry_hub").iloc[0]
    return {
        "meta": meta("Henry Hub daily spot price", "EIA API (series RNGWHHD)",
                     f"{hh['date'].min():%Y-%m-%d} to {hh['date'].max():%Y-%m-%d}", False),
        "headline": {"record_price": clean(top["henry_hub"], 2), "record_day": clean(top["date"]),
                     "latest_price": clean(hh["henry_hub"].iloc[-1], 2), "latest_day": clean(hh["date"].iloc[-1])},
        "daily": columns(hh.rename(columns={"henry_hub": "price"}), 2),
        "spikes": records(spikes[["start", "peak_day", "price_before", "peak_price"]], 2),
    }


def export_var() -> dict:
    summary = read("var_backtest_summary.csv")
    storms = read("var_storm_windows.csv", parse_dates=["worst_day"])
    textbook_short = storms[(storms["model"] == "Normal (textbook)") & (storms["side"] == "short")]
    worst = textbook_short.loc[textbook_short["loss_to_var_ratio"].idxmax()]
    textbook = summary[summary["model"] == "Normal (textbook)"]

    # Breaches by year (year filter), recomputed from the same models
    hh = pd.read_csv(DATA_RAW / "henry_hub_daily.csv", parse_dates=["date"]).set_index("date")["henry_hub"]
    _, _, series = var_backtest.run(hh)
    yearly = []
    for (side, model), (loss, fc) in series.items():
        df = pd.concat({"loss": loss, "var": fc}, axis=1).dropna()
        by_year = (df["loss"] > df["var"]).groupby(df.index.year).agg(["sum", "size"])
        for year, row in by_year.iterrows():
            yearly.append({"side": side, "model": model, "year": int(year), "breaches": int(row["sum"]),
                           "days": int(row["size"]), "expected": round(row["size"] * 0.01, 1)})
    return {
        "meta": meta("Does the standard risk number (VaR) work for gas?",
                     "EIA Henry Hub daily spot; 1-day 99% VaR, 250-day window", "1997 to today", False),
        "headline": {
            "worst_miss_ratio": clean(worst["loss_to_var_ratio"], 1), "worst_miss_event": worst["event"],
            "worst_miss_forecast_pct": clean(worst["var_that_day_pct"] * 100, 0),
            "worst_miss_actual_pct": clean(worst["worst_loss_pct"] * 100, 0),
            "textbook_breach_rate_pct": clean(textbook["breach_rate"].mean() * 100, 2), "promised_rate_pct": 1.0,
        },
        "summary": records(summary[["side", "model", "days", "breaches", "expected", "breach_rate", "kupiec_p"]]),
        "storms": records(storms[["side", "model", "event", "breaches", "worst_day", "worst_loss_pct",
                                  "var_that_day_pct", "loss_to_var_ratio"]]),
        "yearly": yearly,
    }


def export_basis() -> dict:
    hedge = read("hedge_effectiveness.csv")
    stats = read("basis_stats.csv")
    season = read("basis_seasonality.csv")
    monthly = read("basis_by_month.csv")
    alg = stats.set_index("hub").loc["Algonquin Citygates"]
    h = hedge.set_index("hub")
    return {
        "meta": meta("Does a Henry Hub hedge protect gas at other hubs?", "EIA-ICE daily hub prices",
                     "March 2014 to December 2017 (the only free daily multi-hub data)", False,
                     "Basis = hub price minus Henry Hub on the same day, only where both traded."),
        "headline": {
            "best_hub": h["r2_monthly"].idxmax(), "best_monthly_effectiveness": clean(h["r2_monthly"].max(), 2),
            "worst_hub": h["r2_monthly"].idxmin(), "worst_monthly_effectiveness": clean(h["r2_monthly"].min(), 2),
            "algonquin_max_basis": clean(alg["max"], 2), "algonquin_max_day": alg["max_day"],
            "algonquin_worst_day_usd_10k": clean(h.loc["Algonquin Citygates", "worst_day_usd_at_10k_per_day"], 0),
        },
        "hubs": records(hedge[["hub", "r2", "r2_monthly", "worst_day_usd_at_10k_per_day", "residual_worst_day"]]
                        .merge(stats[["hub", "mean", "min", "max", "max_day"]], on="hub")
                        .merge(season, on="hub")),
        "by_month": records(monthly, 3),
    }


def export_storage() -> dict:
    reg = read("storage_report_regression.csv")
    groups = read("storage_report_by_group.csv")
    weeks = read("storage_report_weeks.csv", parse_dates=["report_date"])
    weeks = weeks[~weeks["roll_on_report_day"]].dropna(subset=["gap_change_bcf"])
    main = reg[(reg["storage_measure"] == "gap_change_bcf") & (reg["price_move"] == "move_report_day")].iloc[0]
    return {
        "meta": meta("Does Thursday's storage report move the price?",
                     "EIA weekly storage; NYMEX front-month futures", "2015 to today", False,
                     "Analyst forecasts are not free, so 'unexpected' is measured against last week's gap from normal."),
        "headline": {"p_value": clean(main["p_value"], 3), "most_bearish_group_move_pct": clean(
            groups["avg_move_report_day_pct"].iloc[-1], 2), "weeks": int(main["weeks"])},
        "regression": records(reg),
        "groups": records(groups),
        "weeks": records(weeks.assign(move_pct=weeks["move_report_day"] * 100)[
            ["report_date", "gap_change_bcf", "move_pct"]], 2),
    }


def export_positioning() -> dict:
    summary = read("positioning_summary.csv")
    weeks = read("positioning_weeks.csv", parse_dates=["report_date"])
    cot = pd.read_csv(DATA_RAW / "cftc_natgas_positioning.csv", parse_dates=["report_date"])
    trades = summary[summary["situation"] != "not crowded"]
    return {
        "meta": meta("When hedge funds crowd one side, does the price reverse?",
                     "CFTC Commitments of Traders; NYMEX futures", "2010 to today", False),
        "headline": {"min_p_value": clean(trades["p_value"].min(), 2), "max_p_value": clean(trades["p_value"].max(), 2)},
        "summary": records(summary),
        "net_position": columns(cot.assign(net_pct=cot["mm_net_pct_oi"] * 100)[["report_date", "net_pct"]], 2),
        "signals": records(weeks[weeks["signal"] != 0][["report_date", "signal"]]),
    }


def export_book() -> dict:
    daily = read("book_pnl_daily.csv", parse_dates=["date"])
    by_cp = read("book_pnl_by_counterparty.csv")
    margin = daily["new_deals"].sum()
    value = daily["mtm_total"].iloc[-1]
    return {
        "meta": meta("The simulated trading book", "Simulated trades priced on real Henry Hub prices",
                     f"{daily['date'].min():%Y-%m-%d} to {daily['date'].max():%Y-%m-%d}", True,
                     "877 simulated trades, one hub, position limit 25,000 MMBtu/day, 3 cent dealer margin."),
        "headline": {"book_value": clean(value, 0), "margin_captured": clean(margin, 0),
                     "margin_share": clean(margin / value, 2)},
        "daily": columns(daily, 0),
        "by_counterparty": records(by_cp, 0),
    }


def export_credit() -> dict:
    hist = read("credit_exposure_daily.csv", parse_dates=["date"])
    breaches = read("credit_breaches.csv")
    default = read("default_event.csv")
    # Two storm lessons (Winter Storm Fern), both measured against Jan 15, before the storm:
    # 1. storm week: biggest jump in credit use during the spike itself (Jan 20-30)
    # 2. payment lag: biggest rise in unpaid bills on Feb 24, the day before January's gas is paid for
    base = hist[hist["date"] == "2026-01-15"].set_index("name")
    week = hist[(hist["date"] >= "2026-01-20") & (hist["date"] <= "2026-01-30") & (hist["alert"] != "defaulted")]
    week_peaks = week.loc[week.groupby("name")["utilization"].idxmax()].set_index("name")
    week_rise = (week_peaks["utilization"] - base["utilization"].reindex(week_peaks.index)).dropna()
    jump_name = week_rise.idxmax()
    jump = week_peaks.loc[jump_name]
    pay_day = hist[hist["date"] == "2026-02-24"].set_index("name")
    bill_rise = (pay_day["unpaid_sales"] - base["unpaid_sales"].reindex(pay_day.index)).dropna()
    lag_name = bill_rise.idxmax()
    lag = pay_day.loc[lag_name]
    util = hist.pivot(index="date", columns="name", values="utilization").reset_index()
    d = default.iloc[0]
    return {
        "meta": meta("Who owes us money, and when is it dangerous?", "Simulated book and counterparties, real prices",
                     f"{hist['date'].min():%Y-%m-%d} to {hist['date'].max():%Y-%m-%d}", True,
                     "NAESB terms: paid on the 25th of the following month. Amber 75%, red 100% of limit."),
        "headline": {
            "storm_week_name": jump_name, "storm_week_day": clean(jump["date"]),
            "storm_week_utilization": clean(jump["utilization"], 2),
            "storm_week_before": clean(base.loc[jump_name, "utilization"], 2),
            "payment_lag_name": lag_name, "payment_lag_day": "2026-02-24",
            "payment_lag_utilization": clean(lag["utilization"], 2), "payment_lag_owed": clean(lag["unpaid_sales"], 0),
            "payment_lag_before": clean(base.loc[lag_name, "utilization"], 2),
            "default_name": d["name"], "default_day": d["default_date"], "default_loss": clean(d["loss"], 0),
            "loss_without_setoff": clean(d["loss_without_setoff"], 0),
        },
        "utilization": columns(util, 3),
        "breaches": records(breaches),
        "default": records(default, 2),
    }


def export_stress() -> dict:
    summary = read("stress_summary.csv")
    credit = read("stress_credit.csv")
    jump = credit.assign(jump=credit["peak_utilization"] - credit["base_utilization"])
    top = jump.loc[jump["jump"].idxmax()]
    return {
        "meta": meta("What if a past storm hit today's book?", "Real storm price moves applied to the simulated book",
                     "Valuation date = latest price date", True),
        "headline": {"worst_pnl": clean(summary["worst_pnl"].min(), 0), "biggest_jump_name": top["name"],
                     "biggest_jump_storm": top["storm"], "biggest_jump_from": clean(top["base_utilization"], 2),
                     "biggest_jump_to": clean(top["peak_utilization"], 2)},
        "summary": records(summary, 2),
        "credit": records(credit, 3),
    }


def export_matching() -> dict:
    score = read("matching_score.csv")
    exc = read("matching_exceptions.csv")
    planted = score[~score["error"].str.startswith("false")]
    return {
        "meta": meta("Did we book every trade right?", "Simulated confirmations with planted errors", "Whole book",
                     True, "No shared trade ID: trades and confirmations are paired by their details."),
        "headline": {"planted": int(planted["planted"].sum()),
                     "raised": int((planted["found"] + planted["found_on_identical_twin"]).sum()),
                     "on_exact_trade": int(planted["found"].sum()),
                     "false_alarms": int(score.loc[score["error"].str.startswith("false"), "found"].iloc[0])},
        "by_issue": records(exc["issue"].value_counts().rename_axis("issue").reset_index(name="count")),
        "score": records(score),
    }


def export_storm_watch() -> dict:
    spikes = read("storm_watch_spikes.csv", parse_dates=["start", "peak_day"])
    summary = read("storm_watch_summary.csv")
    forecast = read("storm_watch_forecast.csv", parse_dates=["date"])
    s = summary.set_index(summary["measure"].str.strip())["value"]
    keys = {
        "price spike events 2010-today": "spike_events",
        "in the cold season (Nov-Mar)": "cold_season_spikes",
        "cold-season spikes warned (perfect forecast)": "warned_perfect_forecast",
        "cold-season spikes with a watch or warning (perfect forecast)": "watch_or_warning_perfect_forecast",
        "spikes covered by archived forecasts": "spikes_with_archived_forecasts",
        "warned by real forecasts": "warned_real_forecasts",
        "warm-season spikes (not weather-driven by cold)": "warm_season_spikes",
        "warning episodes": "warning_episodes",
        "followed by a price spike": "warnings_followed_by_spike",
        "with no spike (false alarms)": "false_alarms",
    }
    return {
        "meta": meta("Storm Watch: can weather warn us before a spike?", "Open-Meteo forecasts and observed weather",
                     "2010 to today (archived forecasts from January 2024)", False,
                     "Alert rules fixed in advance. Looks 7 days ahead because prices move before the cold arrives."),
        "headline": {keys[k]: int(v) for k, v in s.items()},
        "spikes": records(spikes, 2),
        "forecast": records(forecast, 1),
    }


def export_context() -> dict:
    terminals = pd.read_csv(DATA_REFERENCE / "lng_terminals.csv")
    events = pd.read_csv(DATA_REFERENCE / "lng_events.csv")
    use = pd.read_csv(DATA_REFERENCE / "gas_consumption_by_sector_2025.csv")
    return {
        "meta": meta("Market context", "EIA liquefaction capacity (2026 Q2), EIA Today in Energy, news sources",
                     "2025-2026", False),
        "lng_terminals": records(terminals.drop(columns=["source_url"])),
        "lng_events": records(events),
        "gas_use_2025": records(use),
    }


EXPORTS = {
    "prices": export_prices, "var": export_var, "basis": export_basis, "storage": export_storage,
    "positioning": export_positioning, "book": export_book, "credit": export_credit, "stress": export_stress,
    "matching": export_matching, "storm_watch": export_storm_watch, "context": export_context,
}


def write_all(out: Path = OUT) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for name, fn in EXPORTS.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(fn(), separators=(",", ":"), allow_nan=False))
        sizes[name] = path.stat().st_size
    return sizes


if __name__ == "__main__":
    for name, size in write_all().items():
        print(f"{name:12s} {size / 1024:7.1f} KB")
