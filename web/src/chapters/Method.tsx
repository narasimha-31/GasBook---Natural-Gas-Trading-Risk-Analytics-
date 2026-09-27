import { Chapter } from "../components/Chapter";
import { accentOf } from "../lib/chapters";

const REPO = "https://github.com/narasimha-31/GasBook---Natural-Gas-Trading-Risk-Analytics-";

const SOURCES = [
  { name: "Henry Hub daily spot price, weekly storage, state prices", org: "US Energy Information Administration (EIA) API",
    url: "https://www.eia.gov/opendata/" },
  { name: "Daily prices at seven other hubs, 2014–2017", org: "EIA, republished from ICE",
    url: "https://www.eia.gov/electricity/wholesale/" },
  { name: "Hedge fund positions in natural gas futures", org: "CFTC Commitments of Traders",
    url: "https://publicreporting.cftc.gov/" },
  { name: "Front-month natural gas futures", org: "NYMEX, via Yahoo Finance", url: "https://finance.yahoo.com/quote/NG=F/" },
  { name: "Observed weather, archived and live forecasts", org: "Open-Meteo", url: "https://open-meteo.com/" },
  { name: "LNG plant capacity", org: "EIA U.S. liquefaction capacity, 2026 Q2",
    url: "https://www.eia.gov/naturalgas/data.php" },
];

const REAL = [
  "Every price, storage number, hedge fund position and weather reading",
  "The five storms, the LNG outages and the dates they happened",
  "The risk-number test (chapter 2), the hedge test (3), the signals (4) and the weather test (5)",
];

const SIMULATED = [
  "877 trades, all at Henry Hub, January 2025 to September 2026",
  "Eight counterparties with made-up names, credit limits and payment habits",
  "The confirmations and the 114 errors planted in them",
  "One supplier default during Winter Storm Fern",
];

const LIMITS = [
  "The simulated book is cleaner than a real one: no cancelled deals, no pipeline cuts, and every delivery arrives in full. Treat chapter 6 as a best case.",
  "It trades at one hub. Real desks also carry basis at places like Waha and Houston Ship Channel, whose daily prices are not free.",
  "Free daily prices for other hubs stop at the end of 2017, so the hedge test (chapter 3) covers 2014–2017 only. Nothing after 2017 is estimated.",
  "The dealer margin is set at 3 cents per MMBtu. Real Henry Hub margins are often thinner.",
  "Traders judge the storage report against analyst forecasts, which are not free. Our stand-in understates how much the report moves prices.",
  "The weather alert was tested against real archived forecasts on only four spikes since January 2024. That is too few to call it reliable.",
  "A defaulting counterparty is assumed to pay back nothing. Real bankruptcies usually return something, later.",
];

export function Method() {
  const accent = accentOf("method");
  return (
    <Chapter
      id="method"
      number={8}
      accent={accent}
      question="What is real here, what is simulated, and what are the limits?"
      answer={
        <p>
          All the market data is real and public. The trading book is simulated, because real ones are confidential.
          The code that turns the data into these results is open on GitHub.
        </p>
      }
    >
      <div className="grid gap-10 md:grid-cols-2">
        <div>
          <h3 className="flex items-center gap-3 font-serif text-xl font-semibold">
            Real <span className="stamp text-hedge">Real data</span>
          </h3>
          <ul className="mt-4 space-y-2 text-[1.02rem] text-ink-soft">
            {REAL.map((r) => <li key={r} className="border-l-2 border-hedge/50 pl-3">{r}</li>)}
          </ul>
        </div>
        <div>
          <h3 className="flex items-center gap-3 font-serif text-xl font-semibold">
            Simulated <span className="stamp text-desk">Simulated book</span>
          </h3>
          <ul className="mt-4 space-y-2 text-[1.02rem] text-ink-soft">
            {SIMULATED.map((r) => <li key={r} className="border-l-2 border-desk/50 pl-3">{r}</li>)}
          </ul>
        </div>
      </div>

      <h3 className="mt-14 font-serif text-xl font-semibold">Known limits</h3>
      <ol className="mt-4 list-decimal space-y-3 pl-6 text-[1.02rem] leading-relaxed text-ink-soft marker:text-ink-faint">
        {LIMITS.map((l) => <li key={l}>{l}</li>)}
      </ol>

      <h3 className="mt-14 font-serif text-xl font-semibold">Where the data comes from</h3>
      <div className="mt-4 overflow-x-auto border-y border-rule">
        <table className="w-full min-w-[560px] text-left text-[0.95rem]">
          <tbody>
            {SOURCES.map((s) => (
              <tr key={s.name} className="border-b border-rule/60 last:border-0">
                <td className="py-2.5 pr-4">{s.name}</td>
                <td className="py-2.5">
                  <a className="text-ink-soft underline decoration-rule underline-offset-4 hover:text-ink" href={s.url}
                    target="_blank" rel="noreferrer">{s.org}</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-14 grid gap-8 md:grid-cols-12">
        <div className="md:col-span-7">
          <h3 className="font-serif text-xl font-semibold">How it was built</h3>
          <p className="mt-3 text-[1.02rem] leading-relaxed text-ink-soft">
            Python pulls the data from the public APIs above, keeps the simulated trades in a PostgreSQL database laid
            out like a small trading system, and checks each study with automated tests. A small export step writes
            the results this page reads. The page itself is React and TypeScript, with charts in ECharts.
          </p>
        </div>
        <div className="md:col-span-5">
          <a href={REPO} target="_blank" rel="noreferrer"
            className="block border border-ink/30 p-5 transition-colors hover:border-ink hover:bg-white/60">
            <span className="font-semibold">Read the code on GitHub</span>
            <span className="mt-1 block text-[0.92rem] text-ink-soft">
              Every study, the tests, the data pipeline and this page.
            </span>
          </a>
        </div>
      </div>
    </Chapter>
  );
}
