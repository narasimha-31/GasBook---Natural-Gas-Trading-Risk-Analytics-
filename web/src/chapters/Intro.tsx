import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "../components/Badge";
import { EChart, INK, INK_FAINT, INK_SOFT, MONO, RULE, axisBase, tooltipBase, valueAxisBase, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { useData, type DataFile } from "../lib/data";
import { useNarrow } from "../lib/useNarrow";

interface Prices extends DataFile<{ record_price: number; record_day: string }> {
  daily: { date: string[]; price: number[] };
}

interface Context extends DataFile {
  lng_events: { date_start: string; terminal: string; feedgas_impact_bcfd: number | null }[];
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

// Plain names for the LNG outages in the reference data (dates from data/reference/lng_events.csv)
const LNG_LABEL: Record<string, string> = {
  "2022-06-08": "Freeport LNG fire",
  "2024-07-07": "Hurricane Beryl shuts Freeport LNG",
  "2026-07-01": "Freeport LNG maintenance",
};

// "Jump to" shortcuts: each opens about three months either side of the day
const JUMPS = [
  { label: "2008 commodity boom", day: "2008-07-02" },
  { label: "Winter Storm Uri", day: "2021-02-17" },
  { label: "Freeport LNG fire", day: "2022-06-08" },
  { label: "Jan 2024 arctic blast", day: "2024-01-12" },
  { label: "Winter Storm Fern", day: "2026-01-23" },
];

const DETAIL_SPAN = 1500; // trading days (about 6 years): zoomed in closer than this, show drops and outages
const BIG_DROP = -0.25; // a day the price fell by a quarter or more

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

/**
 * Days the price fell by at least `threshold` from the day before, grouped into runs when they are
 * within `gap` trading days of each other (e.g. the three collapse days after Winter Storm Uri).
 */
function dropRuns(dates: string[], prices: number[], threshold: number, gap = 5) {
  const runs: { days: number[]; before: number; after: number }[] = [];
  for (let i = 1; i < prices.length; i++) {
    if (prices[i] / prices[i - 1] - 1 > threshold) continue;
    const last = runs.at(-1);
    if (last && i - last.days.at(-1)! <= gap) {
      last.days.push(i);
      last.after = prices[i];
    } else {
      runs.push({ days: [i], before: prices[i - 1], after: prices[i] });
    }
  }
  return runs.map((r) => ({
    indices: r.days,
    first: r.days[0],
    change: r.after / r.before - 1,
    tradingDays: r.days.at(-1)! - r.days[0] + 1,
    from: r.before,
    to: r.after,
    startDate: dates[r.days[0]],
  }));
}

function shortDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** Index of the first trading day on or after `iso`. */
function indexOf(dates: string[], iso: string) {
  let lo = 0;
  let hi = dates.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (dates[mid] < iso) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export function Intro() {
  const prices = useData<Prices>("prices");
  const context = useData<Context>("context");
  const narrow = useNarrow();
  const [range, setRange] = useState<[number, number] | null>(null);
  const timer = useRef<number>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const n = prices?.daily.date.length ?? 0;
  const [start, end] = range ?? [0, Math.max(n - 1, 0)];
  const zoomedIn = end - start < DETAIL_SPAN;

  const onZoom = (s: number, e: number) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setRange([s, e]), 150);
  };

  const jump = (day: string) => {
    if (!prices) return;
    const d = prices.daily.date;
    const centre = new Date(`${day}T00:00:00`);
    const before = new Date(centre.getTime() - 90 * 864e5).toISOString().slice(0, 10);
    const after = new Date(centre.getTime() + 90 * 864e5).toISOString().slice(0, 10);
    setRange([indexOf(d, before), Math.min(indexOf(d, after), d.length - 1)]);
  };

  const option = useMemo<Option | null>(() => {
    if (!prices) return null;
    const { date, price } = prices.daily;
    const label = (side: "top" | "left" | "right") => ({
      position: side,
      align: side === "left" ? "right" : side === "right" ? "left" : "center",
      distance: side === "top" ? 8 : 10,
    });

    // Spikes: always shown (phones only have room for the two biggest)
    const spikeMarks = peaks(date, price, narrow ? 20 : 12, 180).map((p) => ({
      coord: [p.date, p.price],
      value: p.price,
      label: {
        ...label(LABEL_SIDE[p.date] ?? "top"),
        formatter: `${NAMED_PEAKS[p.date] ? `{name|${NAMED_PEAKS[p.date]}}\n` : ""}{meta|${shortDate(p.date)}, $${p.price.toFixed(2)}}`,
      },
    }));

    // Big drops: only when zoomed in, otherwise they crowd the 29-year view.
    // One marker per drop day, one label per run of back-to-back drops.
    const dropMarks = zoomedIn
      ? dropRuns(date, price, BIG_DROP)
          .filter((r) => r.first >= start && r.first <= end)
          .flatMap((r) =>
            r.indices.map((i, k) => ({
              coord: [date[i], price[i]],
              value: price[i],
              symbol: "triangle",
              symbolRotate: 180,
              symbolSize: 8,
              itemStyle: { color: "#b0352a" },
              label: k === 0
                ? { show: true, position: "right", distance: 10, align: "left",
                    formatter: `{drop|Down ${Math.abs(Math.round(r.change * 100))}% in ${r.tradingDays} trading day${r.tradingDays > 1 ? "s" : ""}}\n{meta|$${r.from.toFixed(2)} → $${r.to.toFixed(2)} from ${shortDate(r.startDate)}}` }
                : { show: false },
            })),
          )
      : [];

    // LNG outages as labelled lines, also only when zoomed in
    const lngLines = zoomedIn && context
      ? context.lng_events
          .filter((e) => LNG_LABEL[e.date_start])
          .map((e) => ({
            xAxis: e.date_start,
            label: { formatter: `${LNG_LABEL[e.date_start]}${e.feedgas_impact_bcfd != null
              ? ` (${Math.abs(e.feedgas_impact_bcfd).toFixed(1)} Bcf/d of demand lost)` : ""}` },
          }))
      : [];

    return {
      animationDuration: 900,
      grid: { left: 44, right: 20, top: 48, bottom: 56 },
      tooltip: {
        ...tooltipBase,
        formatter: (items: { dataIndex: number }[]) => {
          const i = items[0].dataIndex;
          const change = i > 0 ? price[i] / price[i - 1] - 1 : 0;
          const sign = change > 0 ? "+" : "";
          return `${shortDate(date[i])}<br/><b>$${price[i].toFixed(2)}</b> per MMBtu` +
            (i > 0 ? `<br/>${sign}${(change * 100).toFixed(1)}% on the day` : "");
        },
      },
      xAxis: {
        type: "category",
        data: date,
        ...axisBase,
        axisLabel: {
          ...axisBase.axisLabel,
          // Whole view: label every fifth year. Zoomed in: let ECharts space the labels and show month and year.
          // Whole view: first trading day of every fifth year. Zoomed in: first trading day of each month
          // (every third month when more than two years are showing).
          interval: (i: number, v: string) => {
            if (i === 0) return false;
            const prev = date[i - 1];
            if (!zoomedIn) return +v.slice(0, 4) % 5 === 0 && prev.slice(0, 4) !== v.slice(0, 4);
            const newMonth = prev.slice(0, 7) !== v.slice(0, 7);
            const step = end - start > 520 ? 3 : 1;
            return newMonth && (+v.slice(5, 7) - 1) % step === 0;
          },
          formatter: (v: string) => (zoomedIn ? shortDate(v).replace(/ \d+,/, "") : v.slice(0, 4)),
        },
      },
      yAxis: { type: "value", scale: zoomedIn, ...valueAxisBase, name: "$ per MMBtu", nameLocation: "end",
        nameGap: 14, nameTextStyle: { color: INK_SOFT, fontFamily: MONO, fontSize: 10, align: "left" },
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "${value}" } },
      dataZoom: [
        { type: "inside", startValue: start, endValue: end, zoomOnMouseWheel: false, moveOnMouseWheel: false,
          moveOnMouseMove: !narrow, disabled: narrow },
        { type: "slider", startValue: start, endValue: end, height: 22, bottom: 10, left: 44, right: 20,
          borderColor: RULE, backgroundColor: "rgba(0,0,0,0)", fillerColor: "rgba(47,93,140,0.10)",
          handleStyle: { color: "#faf9f6", borderColor: INK_SOFT }, moveHandleStyle: { color: INK_FAINT },
          dataBackground: { lineStyle: { color: INK_FAINT, width: 0.6 }, areaStyle: { color: "rgba(47,93,140,0.06)" } },
          selectedDataBackground: { lineStyle: { color: "#2f5d8c", width: 0.8 }, areaStyle: { color: "rgba(47,93,140,0.12)" } },
          showDetail: false, brushSelect: false },
      ],
      series: [{
        type: "line",
        data: price,
        showSymbol: false,
        sampling: zoomedIn ? undefined : "lttb",
        lineStyle: { color: "#2f5d8c", width: zoomedIn ? 1.4 : 1.1 },
        areaStyle: { color: "rgba(47, 93, 140, 0.07)" },
        markPoint: {
          symbol: "circle",
          symbolSize: 6,
          itemStyle: { color: INK },
          label: {
            rich: {
              name: { fontFamily: "Source Serif 4, Georgia, serif", fontSize: 13, fontWeight: 600, color: INK, lineHeight: 17 },
              drop: { fontFamily: "Source Serif 4, Georgia, serif", fontSize: 13, fontWeight: 600, color: "#b0352a", lineHeight: 17 },
              meta: { fontFamily: MONO, fontSize: 11, color: INK_SOFT, lineHeight: 15 },
            },
          },
          data: [...spikeMarks, ...dropMarks],
        },
        markLine: {
          symbol: "none",
          silent: true,
          lineStyle: { color: "#2f7f95", type: "dashed", width: 1 },
          label: { position: "end", color: "#2f7f95", fontFamily: MONO, fontSize: 10, distance: 4 },
          data: lngLines,
        },
      }],
    };
  }, [prices, context, narrow, zoomedIn, start, end]);

  return (
    <section id="top" className="pt-8 sm:pt-12">
      <div className="flex items-center justify-between gap-4">
        <p className="text-[0.95rem] text-ink-soft italic">
          US natural gas price at Henry Hub, Louisiana, in dollars per MMBtu, every trading day since January 1997
        </p>
        {prices && <Badge simulated={false} />}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[0.9rem]">
        <span className="text-ink-faint">Jump to</span>
        {JUMPS.map((j) => (
          <button key={j.day} type="button" onClick={() => jump(j.day)}
            className="rounded border border-ink/20 px-2.5 py-0.5 text-ink-soft transition-colors hover:border-ink/50 hover:text-ink">
            {j.label}
          </button>
        ))}
        {range && (
          <button type="button" onClick={() => setRange(null)}
            className="px-1 text-ink-faint underline underline-offset-4 hover:text-ink">
            All years
          </button>
        )}
      </div>

      {prices && (
        <p className="mt-3 text-[0.85rem] text-ink-faint">
          Showing <span className="num text-ink-soft">{shortDate(prices.daily.date[start])}</span> to{" "}
          <span className="num text-ink-soft">{shortDate(prices.daily.date[end])}</span>
        </p>
      )}
      <div className="mt-1 border-y border-rule">
        {option ? (
          <EChart option={option} height={470} merge onZoom={onZoom}
            ariaLabel="US Henry Hub daily gas price from 1997 to 2026, with spikes, big drops and LNG outages labeled" />
        ) : (
          <div className="h-[470px]" />
        )}
      </div>
      <p className="mt-2 text-[0.85rem] text-ink-faint">
        {narrow ? "Drag the handles under the chart to zoom." : "Drag the handles under the chart, or drag across it, to zoom."}{" "}
        Zoomed in, the chart also marks days the price fell by a quarter or more (red) and LNG plant outages (dashed).
      </p>

      <div className="mt-10 grid gap-10 pb-16 md:grid-cols-12 md:gap-12">
        <div className="md:col-span-8">
          <h1 className="font-serif text-4xl leading-[1.15] font-semibold tracking-tight sm:text-5xl">
            Gas marketers live on a few cents a unit. The spikes above are why that is hard.
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-ink-soft">
            A marketer buys gas from producers and sells it to utilities, power plants and LNG terminals. Most days
            the price barely moves and the margin adds up quietly. Then a cold snap arrives and the price jumps
            five or ten times in a few days. This report looks at what those days do to a small US desk: its risk
            numbers, its hedges, the customers who owe it money, and the trades it has to get right.
          </p>
          <p className="mt-4 text-lg leading-relaxed text-ink-soft">
            Everything here is about the US market. The market data is real. The trading book is simulated, because
            real trading books are confidential, and every chapter says which is which.
          </p>
        </div>
        <div className="space-y-6 md:col-span-4">
          <Note term="Henry Hub">
            A pipeline junction in Erath, Louisiana, and the benchmark price for US natural gas. Europe (TTF) and
            Asia (JKM) have their own benchmarks, often several times higher.
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
