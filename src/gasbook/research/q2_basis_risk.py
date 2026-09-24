"""Q2: Is a Henry Hub hedge really protecting gas bought or sold at other hubs?

Data: EIA-ICE daily hub prices, March 2014 - December 2017 (the only free daily multi-hub data).
Basis = hub - Henry Hub on the same delivery day, only where both traded. Nothing is filled in or extrapolated.

Run: python -m gasbook.research.q2_basis_risk
Outputs: reports/q2_*.csv, reports/q2_basis_risk.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gasbook.config import DATA_RAW, ROOT
from gasbook.ingest import eia_ice
from gasbook.risk import basis

REPORTS = ROOT / "reports"
DAILY_VOLUME_MMBTU = 10_000  # a typical small physical deal: 10,000 MMBtu per day
WINTER = [12, 1, 2]


def run(hubs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    wide = eia_ice.to_wide(hubs)
    b = basis.basis_table(wide)

    stats = basis.basis_stats(b, blowout=1.0)
    monthly = basis.monthly_profile(b)

    hedge = pd.DataFrame({
        hub: {**basis.hedge_effectiveness(wide[hub], wide[basis.HENRY]),
              **basis.monthly_hedge_effectiveness(wide[hub], wide[basis.HENRY])}
        for hub in b
    }).T.rename_axis("hub")
    hedge["worst_day_usd_at_10k_per_day"] = hedge["residual_worst_abs"].astype(float) * DAILY_VOLUME_MMBTU
    hedge["p99_day_usd_at_10k_per_day"] = hedge["residual_p99_abs"].astype(float) * DAILY_VOLUME_MMBTU

    season = pd.DataFrame({
        "winter_mean_basis": b[b.index.month.isin(WINTER)].mean(),
        "rest_of_year_mean_basis": b[~b.index.month.isin(WINTER)].mean(),
    })
    # Unhedged basis cost of one 30-day winter month at 10,000 MMBtu/day vs the rest of the year
    season["winter_month_basis_usd_at_10k"] = season["winter_mean_basis"] * DAILY_VOLUME_MMBTU * 30
    return b, stats, monthly, hedge, season


def plot(b: pd.DataFrame, monthly: pd.DataFrame, path) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    for hub in ("Algonquin Citygates", "TETCO-M3", "SoCal Citygate", "Chicago Citygates"):
        s = b[hub].dropna()
        ax1.plot(s.index, s, lw=0.8, label=hub)
    ax1.axhline(0, color="k", lw=0.6)
    ax1.set_title("Daily basis vs Henry Hub, 2014-2017 (EIA-ICE; gaps = no trade that day)")
    ax1.set_ylabel("$/MMBtu")
    ax1.legend(fontsize=8)

    monthly.plot(ax=ax2, marker="o", lw=1)
    ax2.axhline(0, color="k", lw=0.6)
    ax2.set_xticks(range(1, 13))
    ax2.set_title("Average basis by calendar month: winter blowouts in the Northeast")
    ax2.set_ylabel("$/MMBtu")
    ax2.legend(fontsize=7, ncol=4)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    hubs = pd.read_csv(DATA_RAW / "eia_ice_hub_prices_2014_2017.csv", parse_dates=["delivery_start"])
    b, stats, monthly, hedge, season = run(hubs)

    REPORTS.mkdir(exist_ok=True)
    stats.round(4).to_csv(REPORTS / "q2_basis_stats.csv")
    monthly.round(4).to_csv(REPORTS / "q2_basis_by_month.csv")
    hedge.to_csv(REPORTS / "q2_hedge_effectiveness.csv")
    season.round(4).to_csv(REPORTS / "q2_basis_seasonality.csv")
    plot(b, monthly, REPORTS / "q2_basis_risk.png")

    pd.set_option("display.width", 220)
    print("Basis vs Henry Hub ($/MMBtu):")
    print(stats.round(2).to_string())
    print("\nHenry Hub hedge effectiveness (share of daily price risk removed):")
    cols = ["r2", "r2_without_worst_1pct", "r2_monthly", "highly_effective_monthly",
            "residual_worst_day", "worst_day_usd_at_10k_per_day", "p99_day_usd_at_10k_per_day"]
    print(hedge[cols].to_string())
    print("\nSeasonality:")
    print(season.round(2).to_string())
