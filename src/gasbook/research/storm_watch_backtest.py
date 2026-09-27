"""Would Storm Watch have warned before real Henry Hub price spikes, and how early?

1. Observed weather, 2010-today, as if forecasts were perfect: for every price spike event, did the actual weather
   from the spike day through the next 7 days reach warning level? How many warnings had no spike (false alarms)?
2. Archived forecasts, 2024-today (the real test): for spikes since the archive starts, how many days before the
   spike did an actual forecast already show a warning in its 7-day lookahead?
3. Today's 16-day forecast: is there an alert right now?

Run: python -m gasbook.research.storm_watch_backtest   (needs: python -m gasbook.ingest.weather)
Outputs: reports/storm_watch_spikes.csv, reports/storm_watch_summary.csv, reports/storm_watch_forecast.csv,
         reports/storm_watch.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gasbook.book import storm_watch as sw
from gasbook.config import DATA_RAW, ROOT

REPORTS = ROOT / "reports"


def load():
    spot = pd.read_csv(DATA_RAW / "henry_hub_daily.csv", parse_dates=["date"]).set_index("date")["henry_hub"]
    obs = pd.read_csv(DATA_RAW / "weather_observed.csv", parse_dates=["date"])
    past = pd.read_csv(DATA_RAW / "weather_past_forecasts.csv", parse_dates=["date"])
    fc = pd.read_csv(DATA_RAW / "weather_forecast.csv", parse_dates=["date"])
    return spot, obs, past, fc


if __name__ == "__main__":
    spot, obs, past, fc = load()
    spot = spot.loc[obs["date"].min():obs["date"].max()]
    alerts = sw.daily_alerts(obs)
    spikes = sw.spike_events(spot)

    spikes["warned_by_weather"] = [sw.warned(alerts, s) for s in spikes["start"]]
    spikes["watch_or_warning"] = [sw.warned(alerts, s, min_level="watch") for s in spikes["start"]]
    spikes["cold_season"] = spikes["start"].dt.month.isin([11, 12, 1, 2, 3])
    archive_start = past.dropna(subset=["min_temp_f"])["date"].min()
    spikes["forecast_covered"] = spikes["start"] >= archive_start
    spikes["forecast_notice_days"] = [sw.forecast_notice(past, s) if covered else None
                                      for s, covered in zip(spikes["start"], spikes["forecast_covered"])]

    episodes = sw.alert_episodes(alerts)
    spike_starts = spikes["start"]
    # A warning episode is useful if a spike started within the lookahead window before it, up to its last day
    episodes["followed_by_spike"] = [
        bool(((spike_starts >= e.start - pd.Timedelta(days=sw.LOOKAHEAD_DAYS)) & (spike_starts <= e.end)).any())
        for e in episodes.itertuples()
    ]

    winter = spikes[spikes["cold_season"]]
    summary = pd.DataFrame([
        {"measure": "price spike events 2010-today", "value": len(spikes)},
        {"measure": "  in the cold season (Nov-Mar)", "value": len(winter)},
        {"measure": "cold-season spikes warned (perfect forecast)", "value": int(winter["warned_by_weather"].sum())},
        {"measure": "cold-season spikes with a watch or warning (perfect forecast)",
         "value": int(winter["watch_or_warning"].sum())},
        {"measure": "spikes covered by archived forecasts", "value": int(spikes["forecast_covered"].sum())},
        {"measure": "  warned by real forecasts", "value": int(spikes["forecast_notice_days"].notna().sum())},
        {"measure": "warm-season spikes (not weather-driven by cold)", "value": int((~spikes["cold_season"]).sum())},
        {"measure": "warning episodes", "value": len(episodes)},
        {"measure": "  followed by a price spike", "value": int(episodes["followed_by_spike"].sum())},
        {"measure": "  with no spike (false alarms)", "value": int((~episodes["followed_by_spike"]).sum())},
    ])

    fc_alerts = sw.daily_alerts(fc)
    fc_out = fc_alerts[["level", "reason"]].reset_index()
    lows = fc.pivot_table(index="date", columns="site", values="min_temp_f")
    gusts = fc.pivot_table(index="date", columns="site", values="max_gust_mph")
    fc_out["midland_low_f"] = lows[sw.MIDLAND].to_numpy()
    fc_out["houston_low_f"] = lows[sw.HOUSTON].to_numpy()
    fc_out["max_gulf_gust_mph"] = gusts[sw.GULF].max(axis=1).to_numpy()

    REPORTS.mkdir(exist_ok=True)
    spikes.to_csv(REPORTS / "storm_watch_spikes.csv", index=False)
    summary.to_csv(REPORTS / "storm_watch_summary.csv", index=False)
    fc_out.to_csv(REPORTS / "storm_watch_forecast.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(spot.index, spot, color="tab:blue", lw=0.7, label="Henry Hub spot ($/MMBtu)")
    warn_days = alerts.index[alerts["level"] == "warning"]
    ax.scatter(warn_days, [spot.max() * 1.05] * len(warn_days), marker="|", color="tab:red", s=60,
               label="Freeze or hurricane warning (observed weather)")
    for s in spikes.itertuples():
        ax.scatter(s.peak_day, s.peak_price, color="tab:orange" if s.warned_by_weather else "0.4", s=25, zorder=3)
    ax.set_title("Storm Watch backtest: warnings (red ticks) vs Henry Hub price spikes (orange = warned, grey = not)")
    ax.set_ylabel("$/MMBtu")
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(REPORTS / "storm_watch.png", dpi=130)
    plt.close(fig)

    pd.set_option("display.width", 220)
    print(summary.to_string(index=False))
    print("\nCold-season spikes:")
    print(winter[["start", "peak_day", "price_before", "peak_price", "warned_by_weather", "watch_or_warning",
                  "forecast_covered", "forecast_notice_days"]].to_string(index=False))
    print("\nWarm-season spikes:")
    print(spikes[~spikes["cold_season"]][["start", "peak_day", "price_before", "peak_price"]].to_string(index=False))
    active = fc_out[fc_out["level"] != "none"]
    print(f"\nToday's 16-day forecast ({fc_out['date'].min().date()} -> {fc_out['date'].max().date()}): "
          + ("no alert" if active.empty else f"{len(active)} alert days"))
    print(fc_out[["date", "level", "midland_low_f", "houston_low_f", "max_gulf_gust_mph"]].round(
        {"midland_low_f": 1, "houston_low_f": 1, "max_gulf_gust_mph": 1}).head(16)
          .to_string(index=False))
