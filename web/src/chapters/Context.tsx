import { useMemo } from "react";

import { Chapter } from "../components/Chapter";
import { EChart, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";
import { day } from "../lib/format";
import { useNarrow } from "../lib/useNarrow";

interface Terminal {
  project: string;
  operator: string;
  state: string;
  status_eia_2026q2: string;
  baseload_bcfd: number;
}

interface LngEvent {
  date_start: string;
  date_end: string | null;
  event: string;
  terminal: string;
  feedgas_impact_bcfd: number | null;
  price_note: string | null;
  source_url: string;
}

interface ContextData extends DataFile {
  lng_terminals: Terminal[];
  lng_events: LngEvent[];
  gas_use_2025: { sector: string; bcfd_2025: number; share_of_total: number; change_vs_2024: string }[];
}

const STATUS = [
  { key: "Commercial operation", label: "Operating", color: "#2f7f95" },
  { key: "Commissioning", label: "Starting up", color: "#7fb3c2" },
  { key: "Under construction", label: "Under construction", color: "#c9dde3" },
];

// Operators grouped by company so the chart has one bar per company
const COMPANY: Record<string, string> = {
  "Cheniere Energy": "Cheniere",
  "Venture Global LNG": "Venture Global",
  "QatarEnergy / ExxonMobil": "Golden Pass",
  "Freeport LNG Development": "Freeport LNG",
  "Sempra LNG": "Sempra",
  Sempra: "Sempra",
  NextDecade: "NextDecade",
  "Woodside Energy": "Woodside",
  "BHE GT&S (Berkshire Hathaway)": "Cove Point",
  "Kinder Morgan": "Elba Island",
  Kimmeridge: "Commonwealth LNG",
  "Fairwood Group": "Delfin (offshore)",
};

export function Context() {
  const data = useData<ContextData>("context");
  const accent = accentOf("context");
  const narrow = useNarrow();

  const totals = useMemo(() => {
    const t: Record<string, number> = {};
    data?.lng_terminals.forEach((r) => (t[r.status_eia_2026q2] = (t[r.status_eia_2026q2] ?? 0) + r.baseload_bcfd));
    return t;
  }, [data]);

  const useOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const rows = data.gas_use_2025;
    return {
      animationDuration: 800,
      grid: { left: 8, right: 64, top: 8, bottom: 24, containLabel: true },
      tooltip: { ...tooltipBase, trigger: "item",
        formatter: (p: { dataIndex: number }) => `${rows[p.dataIndex].sector}<br/>${rows[p.dataIndex].change_vs_2024}` },
      xAxis: { type: "value", ...valueAxisBase, axisLabel: { ...valueAxisBase.axisLabel, show: !narrow } },
      yAxis: { type: "category", inverse: true, ...axisBase, data: rows.map((r) => r.sector.replace(" (lease/plant/pipeline fuel)", "")),
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: 13 } },
      series: [{ type: "bar", barWidth: "55%",
        data: rows.map((r, i) => ({ value: r.bcfd_2025, itemStyle: { color: i === 0 ? "#2f7f95" : "#b9c3cf" } })),
        label: { show: true, position: "right", fontFamily: MONO, fontSize: 11, color: INK_SOFT,
          formatter: (p: { dataIndex: number; value: number }) =>
            `${p.value} (${Math.round(rows[p.dataIndex].share_of_total * 100)}%)` } }],
    };
  }, [data, narrow]);

  const lngOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const byCompany: Record<string, Record<string, number>> = {};
    data.lng_terminals.forEach((r) => {
      const c = COMPANY[r.operator] ?? r.operator;
      byCompany[c] ??= {};
      byCompany[c][r.status_eia_2026q2] = (byCompany[c][r.status_eia_2026q2] ?? 0) + r.baseload_bcfd;
    });
    const companies = Object.keys(byCompany).sort(
      (a, b) => Object.values(byCompany[b]).reduce((x, y) => x + y, 0) - Object.values(byCompany[a]).reduce((x, y) => x + y, 0),
    );
    return {
      animationDuration: 800,
      grid: { left: 20, right: 16, top: narrow ? 64 : 40, bottom: 24, containLabel: true },
      legend: { top: 0, left: 0, textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, axisPointer: { type: "shadow" }, valueFormatter: (v: number) => `${v.toFixed(2)} Bcf/d` },
      xAxis: { type: "value", ...valueAxisBase, axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}" } },
      yAxis: { type: "category", inverse: true, data: companies, ...axisBase,
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: narrow ? 11 : 13,
          width: narrow ? 110 : 220, overflow: "break" } },
      series: STATUS.map((s) => ({
        name: s.label, type: "bar", stack: "cap", itemStyle: { color: s.color, borderColor: "#faf9f6", borderWidth: 1 },
        data: companies.map((c) => Math.round((byCompany[c][s.key] ?? 0) * 100) / 100 || null),
      })),
    };
  }, [data, narrow]);

  const power = data?.gas_use_2025[0];
  const total = data?.gas_use_2025.reduce((a, r) => a + r.bcfd_2025, 0);

  return (
    <Chapter
      id="context"
      number={7}
      accent={accent}
      meta={data?.meta}
      question="Who buys the gas, and where is new demand coming from?"
      answer={
        power && total && (
          <p>
            Power plants burn the most:{" "}
            <strong className="num text-ink">{power.bcfd_2025}</strong> of the{" "}
            <strong className="num text-ink">{total.toFixed(1)}</strong> billion cubic feet the US used each day in 2025.
            The biggest new buyers are LNG export plants on the Gulf Coast: they can take{" "}
            <strong className="num text-ink">{(totals["Commercial operation"] ?? 0).toFixed(1)}</strong> Bcf a day today,
            and plants starting up or being built add{" "}
            <strong className="num text-ink">
              {((totals["Commissioning"] ?? 0) + (totals["Under construction"] ?? 0)).toFixed(1)}
            </strong>{" "}
            more.
          </p>
        )
      }
      notes={
        <>
          <Note term="Bcf/d">Billion cubic feet per day, about a million MMBtu a day.</Note>
          <Note term="LNG">
            Gas cooled to a liquid so it fits on a ship. The plants buy gas from producers and marketers every day.
          </Note>
          <Note term="Why it matters for a marketer">
            An LNG plant is a huge customer. When one trips offline, gas that was going to it floods the Gulf Coast
            and local prices drop.
          </Note>
        </>
      }
      why="New LNG demand makes Gulf Coast gas more valuable on normal days and more fragile on bad ones. A desk selling to these plants carries their outages and their credit."
    >
      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          <p className="text-[0.95rem] text-ink-soft italic">US gas use by sector in 2025, Bcf per day</p>
          <div className="mt-3 border-y border-rule">
            {useOption && <EChart option={useOption} height={260} ariaLabel="US natural gas use by sector in 2025" />}
          </div>
        </div>
        <div>
          <p className="text-[0.95rem] text-ink-soft italic">US LNG export capacity by company, Bcf per day (EIA, mid-2026)</p>
          <div className="mt-3 border-y border-rule">
            {lngOption && <EChart option={lngOption} height={420} ariaLabel="US LNG export capacity by company and status" />}
          </div>
        </div>
      </div>

      <h3 className="mt-14 font-serif text-xl font-semibold">When an LNG plant goes down</h3>
      <ol className="mt-4 border-t border-rule">
        {data?.lng_events.map((e) => (
          <li key={e.date_start + e.event} className="grid gap-1 border-b border-rule/70 py-3 sm:grid-cols-12 sm:gap-6">
            <span className="num text-[0.85rem] text-ink-soft sm:col-span-2">{day(e.date_start)}</span>
            <span className="sm:col-span-7">
              <span className="font-semibold">{e.terminal === "All" ? "All US LNG plants" : e.terminal}.</span>{" "}
              {e.event}.{e.price_note ? ` ${e.price_note}.` : ""}{" "}
              <a className="text-[0.9rem] text-ink-faint underline underline-offset-4 hover:text-ink" href={e.source_url}
                target="_blank" rel="noreferrer">Source</a>
            </span>
            <span className="num text-[0.85rem] sm:col-span-3 sm:text-right">
              {e.feedgas_impact_bcfd != null ? `${Math.abs(e.feedgas_impact_bcfd).toFixed(1)} Bcf/d of demand lost` : "Contract dispute"}
            </span>
          </li>
        ))}
      </ol>
    </Chapter>
  );
}
