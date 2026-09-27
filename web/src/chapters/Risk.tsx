import { useMemo, useState } from "react";

import { Chapter } from "../components/Chapter";
import { Toggle, YearRange } from "../components/Controls";
import { EChart, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, xName, yName, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";
import { useNarrow } from "../lib/useNarrow";

type Side = "short" | "long";

interface StormRow {
  side: Side;
  model: string;
  event: string;
  worst_day: string;
  worst_loss_pct: number;
  var_that_day_pct: number;
  loss_to_var_ratio: number;
}

interface YearRow {
  side: Side;
  model: string;
  year: number;
  breaches: number;
  expected: number;
}

interface VarData extends DataFile<{
  worst_miss_ratio: number;
  worst_miss_event: string;
  worst_miss_forecast_pct: number;
  worst_miss_actual_pct: number;
  textbook_breach_rate_pct: number;
}> {
  storms: StormRow[];
  yearly: YearRow[];
}

const TEXTBOOK = "Normal (textbook)";
const BETTER = "Filtered historical";
const RED = "#b0352a";
const FAINT = "#b9c3cf";
const INDIGO = "#4b4a8f";

export function Risk() {
  const data = useData<VarData>("var");
  const accent = accentOf("risk");
  const [side, setSide] = useState<Side>("short");
  const narrow = useNarrow();
  const [range, setRange] = useState<[number, number] | null>(null);

  const years = useMemo(() => (data ? [...new Set(data.yearly.map((y) => y.year))].sort() : []), [data]);
  const minYear = years[0] ?? 1998;
  const maxYear = years.at(-1) ?? 2026;
  const [from, to] = range ?? [minYear, maxYear];

  const stormOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const rows = data.storms.filter((r) => r.side === side);
    const events = [...new Set(rows.map((r) => r.event))];
    const pick = (event: string, model: string) => rows.find((r) => r.event === event && r.model === model)!;
    const pct = (v: number) => Math.round(v * 100);
    return {
      animationDuration: 900,
      grid: { left: 8, right: 48, top: narrow ? 64 : 36, bottom: 44, containLabel: true },
      legend: { top: 0, left: 0, itemGap: 22, itemWidth: 12, itemHeight: 10,
        textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, trigger: "axis", axisPointer: { type: "shadow" },
        valueFormatter: (v: number) => `${v}% of the position` },
      xAxis: { type: "value", splitNumber: narrow ? 3 : 7, ...valueAxisBase, ...xName("Loss as % of the position"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      yAxis: { type: "category", data: events, inverse: true, ...axisBase,
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: narrow ? 12 : 13,
          width: narrow ? 104 : 170, overflow: "break" } },
      series: [
        { name: "Textbook risk number said", type: "bar", barGap: "15%", itemStyle: { color: FAINT },
          data: events.map((e) => pct(pick(e, TEXTBOOK).var_that_day_pct)) },
        { name: "Better model said", type: "bar", itemStyle: { color: INDIGO },
          data: events.map((e) => pct(pick(e, BETTER).var_that_day_pct)) },
        { name: "Actual loss on the worst day", type: "bar", itemStyle: { color: RED },
          label: { show: true, position: "right", fontFamily: MONO, fontSize: 11, color: INK_SOFT,
            formatter: (p: { value: number }) => `${p.value}%` },
          data: events.map((e) => pct(pick(e, TEXTBOOK).worst_loss_pct)) },
      ],
    };
  }, [data, side, narrow]);

  const yearOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const sel = years.filter((y) => y >= from && y <= to);
    const get = (model: string, y: number) =>
      data.yearly.find((r) => r.side === side && r.model === model && r.year === y);
    return {
      animationDuration: 700,
      grid: { left: 36, right: 12, top: narrow ? 84 : 60, bottom: 28 },
      legend: { top: 0, left: 0, itemGap: 22, itemWidth: 12, itemHeight: 10,
        textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, axisPointer: { type: "shadow" } },
      xAxis: { type: "category", data: sel.map(String), ...axisBase },
      yAxis: { type: "value", minInterval: 1, ...valueAxisBase, ...yName("Days") },
      series: [
        { name: "Textbook misses", type: "bar", itemStyle: { color: FAINT },
          data: sel.map((y) => get(TEXTBOOK, y)?.breaches ?? null) },
        { name: "Better model misses", type: "bar", itemStyle: { color: INDIGO },
          data: sel.map((y) => get(BETTER, y)?.breaches ?? null) },
        { name: "Promised (1 in 100 days)", type: "line", step: "middle", symbol: "none",
          lineStyle: { color: RED, type: "dashed", width: 1.2 },
          data: sel.map((y) => get(TEXTBOOK, y)?.expected ?? null) },
      ],
    };
  }, [data, side, years, from, to, narrow]);

  const h = data?.headline;

  return (
    <Chapter
      id="risk"
      number={2}
      accent={accent}
      meta={data?.meta}
      question="Does the standard risk number work in a storm?"
      answer={
        h && (
          <p>
            No. Before the {h.worst_miss_event} it said the worst day for a desk that had sold gas ahead would cost{" "}
            <strong className="num text-ink">{h.worst_miss_forecast_pct}%</strong> of the position. The real loss was{" "}
            <strong className="num text-act">{h.worst_miss_actual_pct}%</strong>. A better model helps on ordinary days
            but still reacts the day after a spike.
          </p>
        )
      }
      notes={
        <>
          <Note term="Value at Risk (VaR)">
            A daily estimate: “on 99 days out of 100, the loss should be smaller than this.” Most desks report it every morning.
          </Note>
          <Note term="Sold ahead">
            A desk that promised gas to customers at a fixed price. It loses when prices jump.
          </Note>
          <Note term="Better model">
            Filtered historical simulation: it scales past losses by how jumpy the market is right now.
          </Note>
        </>
      }
      why="Limits set from this number look safe right up to the day they fail. Pair it with storm tests (chapter 7) instead of trusting it alone."
      details={
        yearOption && (
          <div>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <p className="text-[0.95rem] text-ink-soft italic">
                Days each year the loss was bigger than the risk number. It promises about 2 or 3 a year.
              </p>
              <YearRange min={minYear} max={maxYear} from={from} to={to} onChange={(a, b) => setRange([a, b])} />
            </div>
            <div className="mt-4 border-y border-rule">
              <EChart option={yearOption} height={300} ariaLabel="Risk number misses per year" />
            </div>
          </div>
        )
      }
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <p className="text-[0.95rem] text-ink-soft italic">
          Worst single day in each cold spell: what the risk number expected vs what happened
        </p>
        <Toggle label="Desk that" accent={accent} value={side} onChange={setSide}
          options={[{ value: "short", text: "sold ahead" }, { value: "long", text: "bought ahead" }]} />
      </div>
      <div className="mt-4 border-y border-rule">
        {stormOption && <EChart option={stormOption} height={380} ariaLabel="Risk number forecast versus actual loss in five cold spells" />}
      </div>
    </Chapter>
  );
}
