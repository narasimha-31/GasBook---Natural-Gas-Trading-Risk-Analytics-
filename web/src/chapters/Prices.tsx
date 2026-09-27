import { useMemo, useState } from "react";

import { Chapter } from "../components/Chapter";
import { YearRange } from "../components/Controls";
import { EChart, INK_SOFT, axisBase, tooltipBase, valueAxisBase, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";

interface Prices extends DataFile {
  daily: { date: string[]; price: number[] };
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WINTER = new Set([11, 12, 1, 2]);
const BIG_MOVE = 0.2; // a day where the price rises or falls by more than 20%

interface Move {
  year: number;
  month: number;
  size: number; // absolute % change
}

function dailyMoves(dates: string[], prices: number[]): Move[] {
  const out: Move[] = [];
  for (let i = 1; i < prices.length; i++) {
    const change = prices[i] / prices[i - 1] - 1;
    out.push({ year: +dates[i].slice(0, 4), month: +dates[i].slice(5, 7), size: Math.abs(change) });
  }
  return out;
}

export function Prices() {
  const data = useData<Prices>("prices");
  const accent = accentOf("prices");
  const moves = useMemo(() => (data ? dailyMoves(data.daily.date, data.daily.price) : []), [data]);
  const minYear = moves[0]?.year ?? 1997;
  const maxYear = moves.at(-1)?.year ?? 2026;
  const [range, setRange] = useState<[number, number] | null>(null);
  const [from, to] = range ?? [minYear, maxYear];

  const stats = useMemo(() => {
    const inRange = moves.filter((m) => m.year >= from && m.year <= to);
    const big = inRange.filter((m) => m.size > BIG_MOVE);
    const byMonth = MONTHS.map((_, i) => big.filter((m) => m.month === i + 1).length);
    return {
      days: inRange.length,
      calmShare: inRange.filter((m) => m.size < 0.05).length / Math.max(inRange.length, 1),
      big: big.length,
      winterBig: big.filter((m) => WINTER.has(m.month)).length,
      byMonth,
    };
  }, [moves, from, to]);

  const option = useMemo<Option>(() => ({
    animationDuration: 900,
    grid: { left: 40, right: 12, top: 16, bottom: 32 },
    tooltip: { ...tooltipBase, trigger: "item",
      formatter: (p: { name: string; value: number }) => `${p.name}: ${p.value} day${p.value === 1 ? "" : "s"}` },
    xAxis: { type: "category", data: MONTHS, ...axisBase },
    yAxis: { type: "value", minInterval: 1, ...valueAxisBase },
    series: [{
      type: "bar",
      barWidth: "58%",
      data: stats.byMonth.map((v, i) => ({
        value: v,
        itemStyle: { color: WINTER.has(i + 1) ? "#2f5d8c" : "#b9c3cf" },
      })),
      label: { show: true, position: "top", color: INK_SOFT, fontFamily: "IBM Plex Mono, monospace", fontSize: 11,
        formatter: (p: { value: number }) => (p.value ? String(p.value) : "") },
    }],
  }), [stats]);

  return (
    <Chapter
      id="prices"
      number={1}
      accent={accent}
      meta={data?.meta}
      question="How often does the gas price really jump?"
      answer={
        data && (
          <p>
            Rarely, and almost always in winter. On <strong className="num text-ink">{Math.round(stats.calmShare * 100)}%</strong> of
            trading days the price moved less than 5%. It jumped or fell more than 20% on only{" "}
            <strong className="num text-ink">{stats.big}</strong> days, and{" "}
            <strong className="num text-ink">{stats.winterBig}</strong> of them fell between November and February.
          </p>
        )
      }
      notes={
        <>
          <Note term="Spot price">
            The price for gas delivered tomorrow. It reacts to the weather within hours.
          </Note>
          <Note term="Why winter">
            Cold raises heating demand at the same moment wells freeze and produce less.
          </Note>
        </>
      }
      why="A desk can be calm for eleven months and lose its year in a week. Risk limits have to be set for the winter week, not the average day."
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <p className="text-[0.95rem] text-ink-soft italic">
          Days the Henry Hub price moved more than 20%, by calendar month
          {from === to ? `, ${from}` : `, ${from}–${to}`}. Winter months in blue.
        </p>
        <YearRange min={minYear} max={maxYear} from={from} to={to} onChange={(a, b) => setRange([a, b])} />
      </div>
      <div className="mt-4 border-y border-rule">
        <EChart option={option} height={300} ariaLabel="Count of days with price moves over 20 percent, by month" />
      </div>
    </Chapter>
  );
}
