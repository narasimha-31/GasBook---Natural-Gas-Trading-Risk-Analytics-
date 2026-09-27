"""Storm Watch: turn weather into an early warning for the gas desk.

Alert rules (fixed before looking at any storm results):
    freeze watch      Midland TX min <= 20F  or  Houston min <= 32F
    freeze warning    Midland TX min <= 10F  or  Houston min <= 25F
    hurricane warning wind gusts >= 74 mph at a Gulf Coast site

Why these sites: Midland sits on the Permian gas fields, where wells freeze off in hard cold; Houston is the
Gulf Coast demand and LNG hub. It does not predict prices. It says "a storm is coming, check the book".

Price spike (what we want to warn about): Henry Hub spot up 50%+ in a day, or at least 2.5x its 30-day median.
Days within 5 calendar days of each other count as one spike event.

Timing: traders buy on forecasts, so prices spike 2-4 days BEFORE the cold arrives (and a Friday spot trade prices
a whole long weekend). Storm Watch therefore looks forward: on a given day it checks the next LOOKAHEAD_DAYS days
of forecast. A spike counts as warned if, on or before the day it started, the forecast already showed an alert
somewhere in the following LOOKAHEAD_DAYS days.
"""

import pandas as pd

MIDLAND = "Midland TX (Permian gas fields)"
HOUSTON = "Houston TX"
GULF = ["Houston TX", "Erath LA (Henry Hub)", "Sabine Pass LA (LNG)", "Corpus Christi TX (LNG)"]
WATCH = {MIDLAND: 20.0, HOUSTON: 32.0}
WARNING = {MIDLAND: 10.0, HOUSTON: 25.0}
HURRICANE_GUST_MPH = 74.0
LEVELS = {"none": 0, "watch": 1, "warning": 2}
LOOKAHEAD_DAYS = 7


def daily_alerts(weather: pd.DataFrame) -> pd.DataFrame:
    """One row per date: alert level and the reason. `weather` has date, site, min_temp_f[, max_gust_mph]."""
    w = weather.pivot_table(index="date", columns="site", values="min_temp_f", aggfunc="min")
    out = pd.DataFrame(index=w.index)
    out["level"] = "none"
    out["reason"] = ""
    for level, rule in (("watch", WATCH), ("warning", WARNING)):
        for site, limit in rule.items():
            if site not in w:
                continue
            hit = w[site] <= limit
            out.loc[hit, "level"] = level
            out.loc[hit, "reason"] = f"{site.split(' (')[0]} low {limit:.0f}F or colder"
    if "max_gust_mph" in weather:
        g = weather[weather["site"].isin(GULF)].pivot_table(index="date", columns="site", values="max_gust_mph",
                                                              aggfunc="max")
        hurricane = (g >= HURRICANE_GUST_MPH).any(axis=1).reindex(out.index, fill_value=False)
        out.loc[hurricane, "level"] = "warning"
        out.loc[hurricane, "reason"] = f"Gulf Coast gusts {HURRICANE_GUST_MPH:.0f} mph or more"
    out["rank"] = out["level"].map(LEVELS)
    return out


def spike_events(spot: pd.Series, jump: float = 0.5, multiple: float = 2.5, gap_days: int = 5) -> pd.DataFrame:
    """Henry Hub price spike events: start date, peak date and peak price."""
    spot = spot.sort_index()
    median30 = spot.rolling(30, min_periods=20).median().shift(1)
    spike = (spot.pct_change() >= jump) | (spot >= multiple * median30)
    days = spot.index[spike.fillna(False)]
    events, current = [], []
    for d in days:
        if current and (d - current[-1]).days > gap_days:
            events.append(current)
            current = []
        current.append(d)
    if current:
        events.append(current)
    rows = []
    for ev in events:
        window = spot.loc[ev[0]:ev[-1]]
        rows.append({"start": ev[0], "end": ev[-1], "peak_day": window.idxmax(), "peak_price": window.max(),
                     "price_before": float(spot.loc[:ev[0]].iloc[-2]) if len(spot.loc[:ev[0]]) > 1 else None})
    return pd.DataFrame(rows)


def warned(alerts: pd.DataFrame, start: pd.Timestamp, lookahead: int = LOOKAHEAD_DAYS,
           min_level: str = "warning") -> bool:
    """With a perfect forecast: did the weather from the spike day through the next `lookahead` days reach `min_level`?"""
    window = alerts.loc[start: start + pd.Timedelta(days=lookahead)]
    return bool((window["rank"] >= LEVELS[min_level]).any())


def alert_episodes(alerts: pd.DataFrame, min_level: str = "warning", gap_days: int = 3) -> pd.DataFrame:
    """Runs of alert days (at or above `min_level`), merged when less than `gap_days` apart."""
    days = alerts.index[alerts["rank"] >= LEVELS[min_level]]
    runs, current = [], []
    for d in days:
        if current and (d - current[-1]).days > gap_days:
            runs.append(current)
            current = []
        current.append(d)
    if current:
        runs.append(current)
    return pd.DataFrame([{"start": r[0], "end": r[-1], "days": len(r)} for r in runs])


def forecast_notice(past: pd.DataFrame, start: pd.Timestamp, lookahead: int = LOOKAHEAD_DAYS,
                    min_level: str = "warning") -> int | None:
    """Days of notice real archived forecasts gave before a spike started, or None if they never warned.

    A forecast for day x made `lead` days earlier was issued on x - lead. It counts if it was issued on or before
    the spike day and x falls in the spike day's lookahead window. Notice = spike day - issue day.
    """
    best = None
    for lead, grp in past.groupby("lead_days"):
        a = daily_alerts(grp[["date", "site", "min_temp_f"]])
        hits = a.loc[start: start + pd.Timedelta(days=lookahead)]
        for x in hits.index[hits["rank"] >= LEVELS[min_level]]:
            issued = x - pd.Timedelta(days=int(lead))
            if issued <= start:
                notice = (start - issued).days
                best = notice if best is None else max(best, notice)
    return best
