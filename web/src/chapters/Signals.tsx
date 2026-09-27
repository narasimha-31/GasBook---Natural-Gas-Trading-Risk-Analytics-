import { useMemo, useState } from "react";

import { Chapter } from "../components/Chapter";
import { YearRange } from "../components/Controls";
import { EChart, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, yName, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";

interface StorageData extends DataFile<{ p_value: number; most_bearish_group_move_pct: number; weeks: number }> {
  groups: { group: string; weeks: number; avg_move_report_day_pct: number; share_price_up: number }[];
}

interface PositioningData extends DataFile<{ min_p_value: number; max_p_value: number }> {
  summary: { period: string; situation: string; weeks: number; avg_trade_return_pct: number | null;
    win_rate: number | null; p_value: number | null }[];
  net_position: { report_date: string[]; net_pct: number[] };
}

const SLATE = "#5e6a71";
const RED = "#b0352a";

function Verdict({ text, tone }: { text: string; tone: "weak" | "none" }) {
  return <span className={`stamp ${tone === "none" ? "text-act" : "text-watch"}`}>{text}</span>;
}

function Panel({ title, verdict, children, caption }: { title: string; verdict: React.ReactNode;
  children: React.ReactNode; caption: string }) {
  return (
    <div className="border-t border-ink/60 pt-4">
      <div className="flex items-start justify-between gap-4">
        <h3 className="font-serif text-xl font-semibold leading-snug">{title}</h3>
        {verdict}
      </div>
      <p className="mt-2 text-[0.95rem] text-ink-soft italic">{caption}</p>
      <div className="mt-3">{children}</div>
    </div>
  );
}

export function Signals() {
  const storage = useData<StorageData>("storage");
  const pos = useData<PositioningData>("positioning");
  const accent = accentOf("signals");
  const [range, setRange] = useState<[number, number] | null>(null);

  const storageOption = useMemo<Option | null>(() => {
    if (!storage) return null;
    const labels = ["Much less gas than expected", "", "", "", "Much more gas than expected"];
    return {
      animationDuration: 800,
      grid: { left: 44, right: 8, top: 32, bottom: 44 },
      tooltip: { ...tooltipBase, trigger: "item",
        formatter: (p: { dataIndex: number; value: number }) =>
          `${storage.groups[p.dataIndex].weeks} weeks<br/>average move ${p.value.toFixed(2)}%` },
      xAxis: { type: "category", ...axisBase, data: storage.groups.map((_, i) => labels[i] || `${i + 1}`),
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: 11, width: 80,
          overflow: "break", interval: 0 } },
      yAxis: { type: "value", ...valueAxisBase, ...yName("Futures price move that day"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      series: [{
        type: "bar", barWidth: "55%",
        data: storage.groups.map((g) => ({ value: g.avg_move_report_day_pct,
          itemStyle: { color: g.avg_move_report_day_pct < -0.8 ? RED : SLATE } })),
        label: { show: true, position: "top", fontFamily: MONO, fontSize: 11, color: INK_SOFT,
          formatter: (p: { value: number }) => `${p.value.toFixed(1)}%` },
      }],
    };
  }, [storage]);

  const posOption = useMemo<Option | null>(() => {
    if (!pos) return null;
    const trades = pos.summary.filter((s) => s.situation !== "not crowded");
    const periods = [...new Set(trades.map((t) => t.period))];
    const rule = (situation: string) =>
      periods.map((p) => trades.find((t) => t.period === p && t.situation === situation)?.avg_trade_return_pct ?? 0);
    return {
      animationDuration: 800,
      grid: { left: 44, right: 8, top: 84, bottom: 28 },
      legend: { top: 0, left: 0, itemGap: 8, orient: "vertical", textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 12, color: INK_SOFT } },
      tooltip: { ...tooltipBase, axisPointer: { type: "shadow" }, valueFormatter: (v: number) => `${v.toFixed(1)}%` },
      xAxis: { type: "category", data: periods, ...axisBase },
      yAxis: { type: "value", ...valueAxisBase, ...yName("Average return over 4 weeks"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      series: [
        { name: "Sell when funds are crowded long", type: "bar", itemStyle: { color: SLATE },
          data: rule("funds crowded long -> sell") },
        { name: "Buy when funds are crowded short", type: "bar", itemStyle: { color: RED },
          data: rule("funds crowded short -> buy") },
      ],
    };
  }, [pos]);

  const years = useMemo(() => (pos ? pos.net_position.report_date.map((d) => +d.slice(0, 4)) : []), [pos]);
  const minYear = years[0] ?? 2006;
  const maxYear = years.at(-1) ?? 2026;
  const [from, to] = range ?? [minYear, maxYear];

  const netOption = useMemo<Option | null>(() => {
    if (!pos) return null;
    const idx = years.map((y, i) => (y >= from && y <= to ? i : -1)).filter((i) => i >= 0);
    return {
      animationDuration: 700,
      grid: { left: 44, right: 12, top: 28, bottom: 28 },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => `${v.toFixed(1)}% of open contracts` },
      xAxis: { type: "category", data: idx.map((i) => pos.net_position.report_date[i]), ...axisBase,
        axisLabel: { ...axisBase.axisLabel, formatter: (v: string) => v.slice(0, 4) } },
      yAxis: { type: "value", ...valueAxisBase, ...yName("% of all open contracts (+ long, − short)"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      series: [{ type: "line", showSymbol: false, lineStyle: { color: SLATE, width: 1.2 },
        areaStyle: { color: "rgba(94,106,113,0.08)" }, data: idx.map((i) => pos.net_position.net_pct[i]),
        markLine: { symbol: "none", silent: true, lineStyle: { color: INK_SOFT, width: 0.8 }, label: { show: false },
          data: [{ yAxis: 0 }] } }],
    };
  }, [pos, years, from, to]);

  return (
    <Chapter
      id="signals"
      number={4}
      accent={accent}
      meta={storage?.meta}
      question="Do the popular trading signals actually work?"
      answer={
        storage && pos && (
          <p>
            Barely. The weekly storage report moves the price about{" "}
            <strong className="num text-ink">{Math.abs(storage.headline.most_bearish_group_move_pct).toFixed(1)}%</strong>{" "}
            on its most surprising weeks, and the move is over the same day. Betting against hedge funds when they all
            lean one way made no reliable money in either decade tested.
          </p>
        )
      }
      notes={
        <>
          <Note term="Storage report">
            Every Thursday at 10:30 a.m. the US Energy Information Administration (EIA) reports how much gas went
            into or out of storage the week before.
          </Note>
          <Note term="Hedge fund positioning">
            Every Friday the Commodity Futures Trading Commission (CFTC) publishes how many gas futures hedge funds
            hold. Traders watch for everyone crowding one side.
          </Note>
        </>
      }
      why="Knowing what not to trade saves a small desk time and money. The storage number matters for reading the market that morning, not as a strategy."
      details={
        netOption && (
          <div>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <p className="text-[0.95rem] text-ink-soft italic">
                Hedge funds’ net position in Henry Hub futures, as a share of all open contracts
              </p>
              <YearRange min={minYear} max={maxYear} from={from} to={to} onChange={(a, b) => setRange([a, b])} />
            </div>
            <div className="mt-4 border-y border-rule">
              <EChart option={netOption} height={260} ariaLabel="Hedge fund net position over time" />
            </div>
          </div>
        )
      }
    >
      <div className="grid gap-10 md:grid-cols-2">
        {storageOption && (
          <Panel
            title="Thursday storage report"
            verdict={<Verdict text="Weak" tone="weak" />}
            caption={`Average futures move on report day, ${storage?.headline.weeks} weeks split into five groups by how surprising the number was`}
          >
            <EChart option={storageOption} height={260} ariaLabel="Price move by storage surprise group" />
          </Panel>
        )}
        {posOption && (
          <Panel
            title="Betting against crowded hedge funds"
            verdict={<Verdict text="No edge" tone="none" />}
            caption="Average 4-week return of each rule. Neither is reliable; buying against crowded shorts lost money in both periods."
          >
            <EChart option={posOption} height={260} ariaLabel="Contrarian rule returns by period" />
          </Panel>
        )}
      </div>
      <p className="mt-4 text-[0.9rem] text-ink-faint">
        Analyst forecasts for the storage number are not free, so “surprise” is measured against last week’s gap from
        normal, which understates the real effect.
      </p>
    </Chapter>
  );
}
