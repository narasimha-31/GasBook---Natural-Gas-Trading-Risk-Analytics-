import { useMemo } from "react";

import { Chapter } from "../components/Chapter";
import { EChart, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, xName, yName, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";
import { day, money } from "../lib/format";
import { useNarrow } from "../lib/useNarrow";

interface Hub {
  hub: string;
  r2_monthly: number;
  worst_day_usd_at_10k_per_day: number;
  residual_worst_day: string;
  max: number;
  max_day: string;
  winter_mean_basis: number;
  rest_of_year_mean_basis: number;
}

interface BasisData extends DataFile<{
  best_hub: string;
  best_monthly_effectiveness: number;
  worst_hub: string;
  worst_monthly_effectiveness: number;
  algonquin_max_basis: number;
  algonquin_max_day: string;
  algonquin_worst_day_usd_10k: number;
}> {
  hubs: Hub[];
  by_month: Record<string, number>[];
}

const REGION: Record<string, string> = {
  Malin: "West",
  "PG&E Citygate": "West",
  "SoCal Ehrenberg": "West",
  "SoCal Citygate": "West",
  "Chicago Citygates": "Midwest",
  "Algonquin Citygates": "Northeast",
  "TETCO-M3": "Northeast",
};

// Hedge accounting calls a hedge "highly effective" at 80% or more
const GOOD = "#3c8d5a";
const WATCH = "#b98311";
const ACT = "#b0352a";
const colorFor = (v: number) => (v >= 0.8 ? GOOD : v >= 0.5 ? WATCH : ACT);

export function Hedges() {
  const data = useData<BasisData>("basis");
  const accent = accentOf("hedges");
  const narrow = useNarrow();

  const rankOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const hubs = [...data.hubs].sort((a, b) => b.r2_monthly - a.r2_monthly);
    return {
      animationDuration: 900,
      grid: { left: 8, right: 56, top: 24, bottom: 44, containLabel: true },
      tooltip: { ...tooltipBase, trigger: "item",
        formatter: (p: { name: string; value: number }) => `${p.name}: removes ${Math.round(p.value)}% of the risk` },
      xAxis: { type: "value", max: 100, splitNumber: narrow ? 2 : 5, ...valueAxisBase, ...xName("Share of price risk removed"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      yAxis: { type: "category", inverse: true, ...axisBase,
        data: hubs.map((h) => (narrow ? h.hub : `${h.hub}  (${REGION[h.hub]})`)),
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: 13 } },
      series: [{
        type: "bar",
        barWidth: "56%",
        data: hubs.map((h) => ({ value: Math.round(h.r2_monthly * 100), itemStyle: { color: colorFor(h.r2_monthly) } })),
        label: { show: true, position: "right", fontFamily: MONO, fontSize: 11, color: INK_SOFT, formatter: "{c}%" },
        markLine: {
          symbol: "none",
          lineStyle: { color: INK_SOFT, type: "dashed" },
          label: { formatter: "80% = works", position: "start", fontFamily: MONO, fontSize: 10, color: INK_SOFT },
          data: [{ xAxis: 80 }],
        },
      }],
    };
  }, [data, narrow]);

  const seasonOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const show = [
      { hub: "Algonquin Citygates", color: ACT },
      { hub: "TETCO-M3", color: WATCH },
      { hub: "Chicago Citygates", color: "#2f5d8c" },
      { hub: "Malin", color: GOOD },
    ];
    return {
      animationDuration: 900,
      grid: { left: 44, right: 12, top: narrow ? 88 : 64, bottom: 28 },
      legend: { top: 0, left: 0, itemGap: 22, textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => `$${v.toFixed(2)}` },
      xAxis: { type: "category", data: months, ...axisBase },
      yAxis: { type: "value", ...valueAxisBase, ...yName("$ per MMBtu above Henry Hub"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "${value}" } },
      series: show.map((s) => ({
        name: s.hub, type: "line", symbol: "circle", symbolSize: 5,
        lineStyle: { color: s.color, width: 1.6 }, itemStyle: { color: s.color },
        data: data.by_month.map((m) => m[s.hub]),
      })),
    };
  }, [data, narrow]);

  const h = data?.headline;
  const alg = data?.hubs.find((x) => x.hub === "Algonquin Citygates");

  return (
    <Chapter
      id="hedges"
      number={3}
      accent={accent}
      meta={data?.meta}
      question="Does a Henry Hub hedge protect gas bought somewhere else?"
      answer={
        h && (
          <p>
            In the West, yes: at {h.best_hub} it removed{" "}
            <strong className="num text-good">{Math.round(h.best_monthly_effectiveness * 100)}%</strong> of the monthly
            price risk. In the Northeast it did almost nothing: at {h.worst_hub} it removed{" "}
            <strong className="num text-act">{Math.round(h.worst_monthly_effectiveness * 100)}%</strong>. Local prices
            there can break away from Henry Hub completely in a cold spell.
          </p>
        )
      }
      notes={
        <>
          <Note term="Hedge">
            A second deal that cancels the risk of the first. Sold gas at a fixed price? Buy futures so a price rise
            doesn’t hurt.
          </Note>
          <Note term="Basis">
            The gap between a local hub’s price and Henry Hub. A Henry Hub hedge does not cover it.
          </Note>
          {alg && h && (
            <Note term="The worst day">
              On {day(h.algonquin_max_day)}, gas at Algonquin (New England) cost ${h.algonquin_max_basis.toFixed(2)} more
              than at Henry Hub. On 10,000 MMBtu a day that one day swung {money(h.algonquin_worst_day_usd_10k)}.
            </Note>
          )}
        </>
      }
      why="A desk moving gas into the Northeast needs basis swaps, contracts that lock in the local gap, not just Henry Hub futures. This one finding decides whether a new region is profitable or a trap."
      details={
        seasonOption && (
          <div>
            <p className="text-[0.95rem] text-ink-soft italic">
              Average gap from Henry Hub by calendar month, dollars per MMBtu. The Northeast blows out every winter.
            </p>
            <div className="mt-4 border-y border-rule">
              <EChart option={seasonOption} height={300} ariaLabel="Average basis by month for four hubs" />
            </div>
          </div>
        )
      }
    >
      <p className="text-[0.95rem] text-ink-soft italic">
        Share of monthly price risk a Henry Hub hedge removed at each hub, 2014–2017. Green works, amber partly, red
        doesn’t.
      </p>
      <div className="mt-4 border-y border-rule">
        {rankOption && <EChart option={rankOption} height={320} ariaLabel="Hedge effectiveness by hub" />}
      </div>
      <p className="mt-3 text-[0.9rem] text-ink-faint">
        Only 2014–2017 is shown because that is the only free daily price data for these hubs. Nothing after 2017 is
        estimated.
      </p>
    </Chapter>
  );
}
