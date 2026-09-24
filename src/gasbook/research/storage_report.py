"""Does Thursday's EIA storage report move the gas price?

Every Thursday at 10:30 ET, EIA reports how much gas went into (or out of) storage in the week ending the
previous Friday. We compare that change with what is normal for that time of year:

    vs_normal_bcf = this week's storage change - average change for the same week over the previous 5 years

Positive = more gas than normal (bearish, price should fall). Negative = less gas than normal (bullish).

    gap_change_bcf = this week's vs_normal_bcf - last week's vs_normal_bcf

A simple stand-in for what traders expect: that the gap from normal stays about where it was last week.

Limitation: traders compare the report with analyst forecasts (Reuters/Bloomberg polls), which are not free.
They already expect some difference from normal (they watch the weather), so our measure understates
how much the report really moves prices.

Price move = NYMEX front-month futures close on report day vs the day before. Reports landing on a contract
roll (expiry day or the day after) are excluded because NG=F jumps when it switches contracts.
Holiday weeks (report moved to Wednesday/Friday) are mapped to the first trading day on/after Thursday.

Run: python -m gasbook.research.storage_report
Outputs: reports/storage_report_*.csv, reports/storage_report.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from gasbook.config import DATA_RAW, ROOT
from gasbook.ingest.futures import near_expiry

REPORTS = ROOT / "reports"
NEXT_WEEK_DAYS = 5  # trading days after the report, to check whether prices keep moving the same way


def five_year_average_change(storage: pd.DataFrame, tolerance_days: int = 3) -> pd.Series:
    """Average weekly change of the report nearest the same calendar date in each of the previous 5 years.

    Matching by date (within +/- 3 days, so exactly one Friday) avoids week-53 problems at year end.
    NaN unless all 5 prior years have a matching report.
    """
    s = storage.set_index("week_ending")["weekly_change_bcf"].dropna().sort_index()
    dates = s.index

    def avg(week_ending):
        past = []
        for k in range(1, 6):
            target = week_ending - pd.DateOffset(years=k)
            i = dates.searchsorted(target)
            candidates = [j for j in (i - 1, i) if 0 <= j < len(dates)]
            best = min(candidates, key=lambda j: abs(dates[j] - target), default=None)
            if best is None or abs(dates[best] - target) > pd.Timedelta(days=tolerance_days):
                return np.nan
            past.append(s.iloc[best])
        return float(np.mean(past))

    return storage["week_ending"].map(avg)


def build_weeks(storage: pd.DataFrame, futures: pd.DataFrame) -> pd.DataFrame:
    """One row per storage report with the change vs normal and the price moves around it."""
    s = storage.copy()
    s["normal_change_bcf"] = five_year_average_change(s)
    s["vs_normal_bcf"] = s["weekly_change_bcf"] - s["normal_change_bcf"]
    s["gap_change_bcf"] = s["vs_normal_bcf"].diff()
    s["report_target"] = s["week_ending"] + pd.Timedelta(days=6)  # Thursday after week ending

    f = futures.sort_values("date").reset_index(drop=True)
    log_close = np.log(f["close"]).to_numpy()
    pos = f["date"].searchsorted(s["report_target"])  # first trading day on/after Thursday
    valid = (pos >= 1) & (pos + NEXT_WEEK_DAYS < len(f))
    s, pos = s[valid].copy(), pos[valid]

    s["report_date"] = f["date"].to_numpy()[pos]
    s["move_report_day"] = log_close[pos] - log_close[pos - 1]
    s["move_next_week"] = log_close[pos + NEXT_WEEK_DAYS] - log_close[pos]
    # Roll jump lands on expiry day or the day after
    s["roll_on_report_day"] = near_expiry(s["report_date"], before_bdays=0, after_bdays=1).to_numpy()
    # Roll inside the following week: report date is 0-4 business days before an expiry (roll jump the day after)
    s["roll_in_next_week"] = near_expiry(s["report_date"], before_bdays=NEXT_WEEK_DAYS - 1, after_bdays=0).to_numpy()
    return s.dropna(subset=["vs_normal_bcf"]).reset_index(drop=True)


def regress(weeks: pd.DataFrame, y: str, x_col: str) -> dict:
    """Price move regressed on a storage measure (per 10 Bcf), robust standard errors."""
    w = weeks.dropna(subset=[x_col, y])
    fit = sm.OLS(w[y], sm.add_constant(w[x_col] / 10)).fit(cov_type="HC1")
    return {
        "storage_measure": x_col,
        "price_move": y,
        "weeks": int(fit.nobs),
        "pct_move_per_10bcf": fit.params.iloc[1] * 100,
        "t_stat": fit.tvalues.iloc[1],
        "p_value": fit.pvalues.iloc[1],
        "r2": fit.rsquared,
    }


def by_group(weeks: pd.DataFrame, x_col: str = "gap_change_bcf") -> pd.DataFrame:
    """Split reports into 5 equal groups, from 'much less gas than expected' to 'much more gas than expected'."""
    w = weeks.dropna(subset=[x_col]).copy()
    w["group"] = pd.qcut(w[x_col], 5, labels=["1 much less gas than expected", "2", "3", "4",
                                              "5 much more gas than expected"])
    return w.groupby("group", observed=True).agg(
        weeks=("move_report_day", "size"),
        avg_storage_measure_bcf=(x_col, "mean"),
        avg_move_report_day_pct=("move_report_day", lambda r: r.mean() * 100),
        share_price_up=("move_report_day", lambda r: (r > 0).mean()),
    )


def plot(weeks: pd.DataFrame, groups: pd.DataFrame, path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    w = weeks.dropna(subset=["gap_change_bcf"])
    x, y = w["gap_change_bcf"], w["move_report_day"] * 100
    ax1.scatter(x, y, s=8, alpha=0.4)
    slope, intercept = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 50)
    ax1.plot(xs, intercept + slope * xs, color="tab:red", label=f"{slope * 10:.2f}% per 10 Bcf more gas than expected")
    ax1.axhline(0, color="k", lw=0.5)
    ax1.axvline(0, color="k", lw=0.5)
    ax1.set_xlabel("Gap from normal vs last week (Bcf; + = more gas than expected)")
    ax1.set_ylabel("Front-month futures move on report day (%)")
    ax1.set_title("Report-day price move vs unexpected storage change")
    ax1.legend()

    ax2.bar(range(len(groups)), groups["avg_move_report_day_pct"],
            color=["tab:green", "0.6", "0.6", "0.6", "tab:red"])
    ax2.set_xticks(range(len(groups)), [str(i) for i in groups.index], rotation=20, fontsize=8)
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_ylabel("Average report-day move (%)")
    ax2.set_title("Average move by group")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    storage = pd.read_csv(DATA_RAW / "storage_weekly.csv", parse_dates=["week_ending"])
    futures = pd.read_csv(DATA_RAW / "ng_front_month.csv", parse_dates=["date"])
    weeks = build_weeks(storage, futures)
    day = weeks[~weeks["roll_on_report_day"]]
    week = weeks[~weeks["roll_on_report_day"] & ~weeks["roll_in_next_week"]]

    results = pd.DataFrame([
        regress(day, "move_report_day", "vs_normal_bcf"),
        regress(day, "move_report_day", "gap_change_bcf"),
        regress(week, "move_next_week", "gap_change_bcf"),
    ])
    groups = by_group(day)

    REPORTS.mkdir(exist_ok=True)
    weeks.to_csv(REPORTS / "storage_report_weeks.csv", index=False)
    results.round(4).to_csv(REPORTS / "storage_report_regression.csv", index=False)
    groups.round(4).to_csv(REPORTS / "storage_report_by_group.csv")
    plot(day, groups, REPORTS / "storage_report.png")

    pd.set_option("display.width", 200)
    print(f"{len(weeks)} reports {weeks['report_date'].min().date()} -> {weeks['report_date'].max().date()}; "
          f"{len(day)} used for report-day moves, {len(week)} for next-week moves\n")
    print(results.round(4).to_string(index=False))
    print()
    print(groups.round(3).to_string())
