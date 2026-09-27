# GasBook

How small US natural gas trading desks lose money, and what they can do about it.

**Read the report:** https://narasimha-31.github.io/GasBook---Natural_Gas_Trading_Risk_Analytics/

---

## The short version

A gas marketer is a middleman. It buys gas from producers, pays a pipeline to move it, and sells it to utilities, power plants, factories and the plants that turn gas into liquid for export (LNG plants). It keeps a few cents on every unit. Most days the price barely moves and those cents add up quietly. Then a cold snap arrives, the price jumps five or ten times in a few days, and a year of careful work can disappear in a week.

I wanted to understand exactly where that money goes. So I took 29 years of public US market data, built a simulated trading desk on top of real prices, and asked the questions a small desk asks itself every day: Does the risk number hold up in a storm? Do the hedges actually protect the desk? Who owes it money, and when does that become dangerous? Was every trade booked the way the other side booked it?

Everything here is about the US market. The prices are real. The trades are made up, because real trading books are confidential.

---

## What the data showed

These come from real, public data.

**1. The price is calm almost all the time, and violent in winter.**
On 81% of trading days since 1997, the Henry Hub price moved less than 5%. It jumped or fell more than 20% on only 85 days, and 68 of those days fell between November and February. The record was $30.72 on January 23, 2026, during Winter Storm Fern, higher than anything during Winter Storm Uri in 2021.

**2. The standard risk number fails exactly when it is needed.**
Most desks report a daily number called value at risk: "on 99 days out of 100, the loss should be smaller than this." I tested four versions of it against every trading day since 1997. All of them were wrong more often than they promised. Worst case: before the January 2024 cold snap, the textbook version said a desk that had sold gas ahead would lose at most 15% of the position on its worst day. The real loss was 319%, more than 21 times worse. A smarter version cut the misses during storms from 11 to 4 for a desk that had bought ahead, but it still reacted a day after each spike, because it only looks backward.

**3. A hedge at Henry Hub protects you in some places and not others.**
Most small desks protect themselves with futures priced at Henry Hub in Louisiana. That worked well in the West: it removed 91% of the monthly price risk at Malin in Oregon. In the Northeast it did almost nothing, around 1 to 2%. On December 27, 2017, gas in New England (the Algonquin hub) cost $49.52 more than at Henry Hub. On a normal-sized position of 10,000 MMBtu a day, that one day swung about $348,000. This is based on 2014 to 2017, the only years with free daily prices for these hubs.

**4. The popular trading signals are weak.**
The government's weekly storage report, published every Thursday, moves the price by about 1% on its most surprising weeks, and the move is over the same day. Betting against hedge funds when they all lean the same way made no reliable money in either of two decades tested. Knowing what not to trade is useful too.

**5. The storage number can be forecast from the weather, well enough to matter.**
I built a model that forecasts Thursday's storage number from temperatures in 12 cities, last week's report, the time of year and holiday weeks. Tested on 246 weeks from 2022 on, each year forecast by a model trained only on the years before it, it missed by 13.5 billion cubic feet on average. The usual starting guess, the five-year average for the same week, missed by 31.7. In winter the gap is wider: 14.5 against 53.9. Measured against the model instead of against last week, a surprise moved the price about 0.27% per 10 billion cubic feet, five times the simple measure. Almost all of that comes from 2016 to 2021; since 2022 the effect is small enough to be chance. Each forecast is saved to a log before the report comes out, so it can be checked later.

**6. Weather drives the spikes, but the market moves first.**
Severe cold arrived within a week of 5 of the 7 winter price spikes since 2010. But prices move on the forecast, two to four days before the cold actually arrives. Using the forecasts people really had at the time, a simple freeze alert warned before Winter Storm Fern with two days' notice, missed one other spike by a single degree, and raised 11 false alarms out of 17. Useful as a reminder to check the book, not as a price forecast.

**7. Power plants use the most gas, and LNG plants are the fastest-growing buyers.**
Power plants burned 35.8 of the 92 billion cubic feet the US used each day in 2025. Plants that cool gas into liquid for export can take about 11.4 billion cubic feet a day today, with about 19.6 more starting up or under construction along the Gulf Coast.

---

## What the simulated desk showed

These come from a made-up trading book valued at real prices: 877 trades at Henry Hub from January 2025 to September 2026, with eight fictional customers and suppliers. They show how a problem plays out, not proof about any real company.

**The money comes from the margin, not from betting on price.** Of the book's $10.1 million value, $8.0 million is the few cents locked in on every deal. A position limit keeps the desk from betting big in either direction.

**The dangerous day for credit comes a month after the storm.** Under the standard contract, gas delivered in January is paid for on February 25. So January's storm-priced gas turns into unpaid bills that sit on the books for weeks. One LNG buyer went from 51% of its credit limit before Winter Storm Fern to 136% on February 24, owing $26.9 million, a month after the weather had cleared.

**Suppliers can be a bigger risk than customers.** If you bought gas at a fixed $3 and the price jumps to $21, that contract is suddenly worth a lot to you. If the producer's wells freeze and it stops delivering, you have to buy replacement gas at storm prices. Replaying Winter Storm Uri on today's book, one producer went from owing nothing to 391% of its limit.

**One contract clause saved almost $14 million.** When a simulated producer stopped delivering in the middle of Winter Storm Fern, replacing its gas would have cost $13.95 million. But the desk still owed that producer $16.59 million for gas already delivered, and the contract let it keep that money against the cost. The loss was zero. Without that clause, it would have been $13.95 million.

**Every booking error was caught.** I planted 114 mistakes in the other side's trade records: wrong prices, wrong volumes, wrong customer, wrong delivery month, missing records and records for trades that never happened. The checker flagged all 114 with no false alarms, across 877 trades in under a second. Two landed on an identical twin trade, which is why real trade records carry a shared deal number.

---

## What a desk can do about it

I built working tools for each problem and wrote down what the results suggest. These are recommendations and prototypes. None of them has been tested inside a real company's book yet.

| Problem | What the project built | What it suggests a desk do |
|---|---|---|
| The risk number fails in storms | Tests of four risk models, and replays of five real storms on the current book | Keep the daily number, but set limits from storm replays, not from average days |
| Hedges miss local prices | A measure of how much of the risk a Henry Hub hedge removes at each hub | In the Northeast, add contracts that lock in the local price gap, not just Henry Hub futures |
| Storm bills pile up unpaid | A daily credit monitor that follows each customer's unpaid gas and future deals against its limit | Ask for collateral before storm bills fall due, and watch February as closely as January |
| Suppliers fail in freezes | Credit checks that count what suppliers owe you in value, not just what customers owe you in cash | Treat producers as credit risks, and make sure every contract allows set-off |
| Booking mistakes | A checker that pairs every trade with the other side's record without needing a shared ID | Check every trade record the morning after, not at month-end |
| Thursday's number catches the desk out | A weekly storage forecast with a likely range, a what-if for warmer or colder weather, and a log that scores every forecast | Have a fair estimate before 10:30 on Thursday, and judge the price move against it |
| Storms arrive with little notice | A freeze and hurricane alert from free 16-day weather forecasts | Use it as a prompt to review the book, not as a trading signal |

---

## Words you will see in the report

**Henry Hub.** A pipeline junction in Erath, Louisiana. Its price is the benchmark for US natural gas. Europe (TTF, in the Netherlands) and Asia (JKM, for Japan and Korea) have their own benchmarks, often several times higher.

**MMBtu.** Million British thermal units, the unit wholesale gas is bought and sold in.

**Bcf/d.** Billion cubic feet per day, about a million MMBtu a day. Used for big flows like a pipeline or an LNG plant.

**Spot price.** The price for gas delivered tomorrow. It reacts to the weather within hours.

**Futures.** Contracts to buy or sell gas for delivery in a future month, traded on the New York Mercantile Exchange (NYMEX). The front month is the next month to be delivered.

**Hedge.** A second deal that cancels the risk of the first. Sold gas to a customer at a fixed price? Buy futures so a price rise doesn't hurt.

**Basis.** The gap between a local hub's price and Henry Hub. A Henry Hub hedge does not cover it.

**Value at risk.** A daily estimate of the most a desk should lose on a normal bad day.

**Credit limit.** The most a customer or supplier is allowed to owe the desk.

**Set-off, or netting.** If a counterparty fails, what you owe it can be kept against what it owes you.

**NAESB contract.** The standard US gas contract, written by the North American Energy Standards Board. Gas delivered in one month is paid for on the 25th of the next.

**Counterparty.** Anyone the desk trades with: a producer, utility, power plant, factory or LNG plant.

**Confirmation.** The other side's written record of a trade, checked against the desk's own booking.

**LNG (liquefied natural gas).** Gas cooled to about minus 260°F so it turns liquid and fits on a ship.

**Feedgas.** The gas flowing into an LNG plant each day. When a plant goes down, that demand disappears and local prices drop.

**Train.** One processing line inside an LNG plant. Large plants have several, and maintenance often takes one or two offline at a time.

**Cargo.** One shipload of LNG. Plants cancel cargoes when a storm or outage cuts their supply.

**Commissioning.** The start-up period before a new LNG plant is declared fully running. Venture Global sold cargoes on the open market during a long commissioning period at its Calcasieu Pass plant, and an arbitration panel later ruled for BP, one of its long-term buyers.

**Take-or-pay.** An LNG contract where the buyer pays a fixed fee whether or not it takes the cargo. Cheniere sells this way.

**Tolling.** An LNG contract where the customer brings its own gas and pays the plant a fee to turn it into liquid. Freeport LNG works this way.

**Freeze-off.** When wells stop producing in extreme cold because water in the lines freezes. It cuts supply at the same moment heating demand jumps.

---

## What is real and what is not

**Real:** every price, storage number, hedge fund position and weather reading; the storms, LNG outages and their dates; the risk, hedge, signal, storage forecast and weather studies.

**Simulated:** the 877 trades, the eight counterparties and their credit limits and payment habits, the 114 planted errors, and one supplier default.

**Known limits, in plain words:**
- The simulated book is cleaner than a real one: no cancelled deals, no pipeline cuts, and every delivery arrives in full. Treat the desk results as a best case.
- It trades at one hub. Real desks also carry price gaps at places like Waha in West Texas and the Houston Ship Channel, whose daily prices are not free.
- Free daily prices for other hubs stop at the end of 2017, so the hedge study covers 2014 to 2017 only. Nothing after 2017 is estimated.
- The desk's margin is set at 3 cents per MMBtu. Real margins at Henry Hub are often thinner.
- Traders judge the storage report against analyst forecasts, which are not free. The stand-ins used here, last week's gap and the storage model, still understate how much the report moves prices.
- The storage model's holiday and production inputs were added after looking at its misses from 2022 on, so its test score is slightly flattering. The forecast log is the clean test.
- The weather alert was tested against real archived forecasts on only four spikes since January 2024. That is too few to call it reliable.
- A failed counterparty is assumed to pay back nothing. Real bankruptcies usually return something, later.

---

## Where the data comes from

- US Energy Information Administration (EIA): daily Henry Hub price, weekly storage, state prices, LNG plant capacity
- EIA, republished from the Intercontinental Exchange (ICE): daily prices at seven other hubs, 2014 to 2017
- Commodity Futures Trading Commission (CFTC): weekly hedge fund positions in gas futures
- New York Mercantile Exchange (NYMEX), through Yahoo Finance: front-month gas futures
- Open-Meteo: observed weather, archived forecasts and 16-day forecasts

---

## Running it yourself

You only need this if you want to rebuild the numbers. The report above works without it.

You will need Python 3.12, PostgreSQL, Node.js, and a free EIA data key from https://www.eia.gov/opendata/register.php.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
copy .env.example .env
```

Put your EIA key and PostgreSQL password in `.env`, then pull the data, build the database and run the studies:

```bash
python -m gasbook.ingest.eia
python -m gasbook.ingest.eia_ice
python -m gasbook.ingest.cftc
python -m gasbook.ingest.futures
python -m gasbook.ingest.weather
python -m gasbook.ingest.demand_weather
python -m gasbook.book.database
python -m gasbook.research.var_backtest
python -m gasbook.research.basis_risk
python -m gasbook.research.storage_model
python -m gasbook.research.storage_live
python -m gasbook.research.storage_report
python -m gasbook.research.hedge_fund_positioning
python -m gasbook.research.book_pnl
python -m gasbook.research.credit_monitor
python -m gasbook.research.stress_tests
python -m gasbook.research.trade_matching
python -m gasbook.research.default_event
python -m gasbook.research.storm_watch_backtest
python -m gasbook.export_dashboard
pytest
```

The report itself lives in `web/`:

```bash
cd web
npm install
npm run dev
```

It publishes to GitHub Pages automatically on every push.

---

## How it is built

Python pulls the data from the public sources above, keeps the simulated trades in a PostgreSQL database laid out like a small trading system, and checks every study with automated tests. The storage forecast averages a linear regression and a small gradient-boosted tree model (scikit-learn). A small export step writes the results into files the report reads. The report is a static web page built with React and TypeScript, with charts drawn by ECharts.
