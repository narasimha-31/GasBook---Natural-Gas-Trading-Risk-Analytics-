import { useMemo } from "react";

import { Badge } from "../components/Badge";
import { EChart, INK, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { useData, type DataFile } from "../lib/data";
import { useNarrow } from "../lib/useNarrow";

interface Prices extends DataFile<{ record_price: number; record_day: string }> {
  daily: { date: string[]; price: number[] };
}

// Only peaks whose cause is documented get a name; the rest show date and price only.
const NAMED_PEAKS: Record<string, string> = {
  "2008-07-02": "2008 commodity boom",
  "2021-02-17": "Winter Storm Uri",
  "2024-01-12": "Jan 2024 arctic blast",
  "2026-01-23": "Winter Storm Fern",
};

// Where each label sits relative to its point, so neighbours don't collide.
const LABEL_SIDE: Record<string, "top" | "left" | "right"> = {
  "2003-02-25": "top",
  "2005-12-13": "top",
  "2008-07-02": "right",
  "2021-02-17": "left",
  "2024-01-12": "left",
  "2026-01-23": "left",
};

/** Local maxima above a price floor, at least `gap` points apart. */
function peaks(dates: string[], prices: number[], floor: number, gap = 20) {
  const out: { date: string; price: number }[] = [];
  for (let i = 0; i < prices.length; i++) {
    const lo = Math.max(0, i - gap);
    const hi = Math.min(prices.length, i + gap + 1);
    let isMax = prices[i] >= floor;
    for (let j = lo; j < hi && isMax; j++) if (prices[j] > prices[i]) isMax = false;
    if (isMax) out.push({ date: dates[i], price: prices[i] });
  }
  return out;
}

function shortDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function Intro() {
  const prices = useData<Prices>("prices");
  const narrow = useNarrow();

  const option = useMemo<Option | null>(() => {
    if (!prices) return null;
    const { date, price } = prices.daily;
    // Phones only have room for the three biggest spikes
    const marks = peaks(date, price, narrow ? 18 : 12, 180).map((p) => {
      const side = LABEL_SIDE[p.date] ?? "top";
      return {
        coord: [p.date, p.price],
        value: p.price,
        label: {
          position: side,
          align: side === "left" ? "right" : side === "right" ? "left" : "center",
          distance: side === "top" ? 8 : 10,
          formatter: `${NAMED_PEAKS[p.date] ? `{name|${NAMED_PEAKS[p.date]}}\n` : ""}{meta|${shortDate(p.date)}, $${p.price.toFixed(2)}}`,
        },
      };
    });
    return {
      animationDuration: 1400,
      grid: { left: 44, right: 20, top: 40, bottom: 36 },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => `$${v.toFixed(2)}` },
      xAxis: {
        type: "category",
        data: date,
        ...axisBase,
        // Label the first trading day of every fifth year
        axisLabel: {
          ...axisBase.axisLabel,
          interval: (i: number, v: string) => +v.slice(0, 4) % 5 === 0 && (i === 0 || date[i - 1].slice(0, 4) !== v.slice(0, 4)),
          formatter: (v: string) => v.slice(0, 4),
        },
      },
      yAxis: { type: "value", ...valueAxisBase, axisLabel: { ...valueAxisBase.axisLabel, formatter: "${value}" } },
      series: [{
        type: "line",
        data: price,
        showSymbol: false,
        sampling: "lttb",
        lineStyle: { color: "#2f5d8c", width: 1.1 },
        areaStyle: { color: "rgba(47, 93, 140, 0.07)" },
        markPoint: {
          symbol: "circle",
          symbolSize: 6,
          itemStyle: { color: INK },
          label: {
            rich: {
              name: { fontFamily: "Source Serif 4, Georgia, serif", fontSize: 13, fontWeight: 600, color: INK,
                lineHeight: 17 },
              meta: { fontFamily: MONO, fontSize: 11, color: INK_SOFT, lineHeight: 15 },
            },
          },
          data: marks,
        },
      }],
    };
  }, [prices, narrow]);

  return (
    <section id="top" className="pt-8 sm:pt-12">
      <div className="flex items-center justify-between gap-4">
        <p className="text-[0.95rem] text-ink-soft italic">
          Henry Hub spot price in dollars per MMBtu, every trading day since January 1997
        </p>
        {prices && <Badge simulated={false} />}
      </div>

      <div className="mt-2 border-y border-rule">
        {option ? (
          <EChart option={option} height={440} ariaLabel="Henry Hub daily gas price from 1997 to 2026, with price spikes labeled" />
        ) : (
          <div className="h-[440px]" />
        )}
      </div>

      <div className="mt-10 grid gap-10 pb-16 md:grid-cols-12 md:gap-12">
        <div className="md:col-span-8">
          <h1 className="font-serif text-4xl leading-[1.15] font-semibold tracking-tight sm:text-5xl">
            Gas marketers live on a few cents a unit. The spikes above are why that is hard.
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-ink-soft">
            A marketer buys gas from producers and sells it to utilities, power plants and LNG terminals. Most days
            the price barely moves and the margin adds up quietly. Then a cold snap arrives and the price jumps
            five or ten times in a few days. This report looks at what those days do to a small desk: its risk
            numbers, its hedges, the customers who owe it money, and the trades it has to get right.
          </p>
          <p className="mt-4 text-lg leading-relaxed text-ink-soft">
            The market data is real. The trading book is simulated, because real trading books are confidential,
            and every chapter says which is which.
          </p>
        </div>
        <div className="space-y-6 md:col-span-4">
          <Note term="Henry Hub">
            A pipeline junction in Erath, Louisiana. Its price is what the news means by “the price of natural gas”.
          </Note>
          <Note term="MMBtu">
            Million British thermal units, the unit wholesale gas is bought and sold in.
          </Note>
          <Note term="Marketer">
            A middleman: buys gas, pays a pipeline to move it, sells it elsewhere. Does not drill wells.
          </Note>
        </div>
      </div>
    </section>
  );
}

