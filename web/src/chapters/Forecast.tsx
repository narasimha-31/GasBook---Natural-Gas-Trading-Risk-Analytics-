import { useMemo, useState } from "react";

import { Chapter } from "../components/Chapter";
import { YearRange } from "../components/Controls";
import { EChart, INK, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, xName, yName,
  type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";
import { useNarrow } from "../lib/useNarrow";
import { day, pct } from "../lib/format";

interface Slope { weeks: number; pct_per_10bcf: number; p_value: number }

interface ForecastData extends DataFile<{
  last_week_ending: string; last_change_bcf: number; last_storage_bcf: number; model_miss_bcf: number;
  benchmark_miss_bcf: number; model_within_10: number; test_weeks: number;
}> {
  next: { week_ending: string; report_date: string; kind: string; forecast_bcf: number; low_bcf: number;
    high_bcf: number; forecast_weather_share: number }[];
  what_if: { shift_f: number[]; forecast_bcf: number[] };
  log: { made_on: string; week_ending: string; report_date: string; kind: string; forecast_bcf: number;
    low_bcf: number; high_bcf: number; actual_bcf: number | null; miss_bcf: number | null }[];
  scores: { model: string; mae_bcf: number; share_within_10bcf: number; mae_winter_bcf: number;
    mae_summer_bcf: number; worst_miss_bcf: number; worst_miss_week: string }[];
  history: { week_ending: string[]; actual: number[]; blend: number[]; bench_5yr_avg: number[] };
  weather_effect: Record<string, { heating: number; cooling: number }>;
  holidays: { thanksgiving: number; christmas: number; new_year: number };
  surprise: { groups: { group: string; weeks: number; avg_move_report_day_pct: number; share_price_up: number }[];
    all: Slope; simple: Slope; early: Slope; recent: Slope };
}

const GREEN = "#4f7a3a";
const SLATE = "#5e6a71";
const RED = "#b0352a";
const GUESS = "#b4aa98";

const MODEL_NAMES: Record<string, string> = {
  bench_5yr_avg: "Five-year average for the same week",
  bench_last_gap: "Last week’s gap from average, carried forward",
  blend: "This model",
};

/** +79 Bcf into storage, -120 Bcf out of storage */
const bcf = (v: number, digits = 0) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)} Bcf`;
/** -0.38 -> "−0.38%" */
const signedPct = (v: number) => `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}%`;

function RangeBar({ low, high, value, accent }: { low: number; high: number; value: number; accent: string }) {
  // Scale padded around the range so the ends never touch the edges
  const pad = (high - low) * 0.35;
  const min = low - pad;
  const span = high + pad - min;
  const at = (v: number) => `${((v - min) / span) * 100}%`;
  return (
    <div className="relative mt-5 h-12" aria-hidden="true">
      <div className="absolute top-3 right-0 left-0 h-px bg-rule" />
      <div className="absolute top-1.5 h-3 rounded-sm opacity-25" style={{ left: at(low), width: `calc(${at(high)} - ${at(low)})`, background: accent }} />
      <div className="absolute top-0 h-6 w-0.5" style={{ left: at(value), background: INK }} />
      <span className="num absolute top-6 -translate-x-1/2 text-[0.8rem] text-ink-faint" style={{ left: at(low) }}>{low.toFixed(0)}</span>
      <span className="num absolute top-6 -translate-x-1/2 text-[0.8rem] text-ink-faint" style={{ left: at(high) }}>{high.toFixed(0)}</span>
    </div>
  );
}

export function Forecast() {
  const data = useData<ForecastData>("storage_model");
  const accent = accentOf("forecast");
  const [shift, setShift] = useState(0);
  const [range, setRange] = useState<[number, number] | null>(null);
  const narrow = useNarrow();

  const h = data?.headline;
  const next = data?.next.find((n) => n.kind === "next report");
  const projection = data?.next.find((n) => n.kind === "projection");

  const whatIf = useMemo(() => {
    if (!data) return null;
    const at = (s: number) => data.what_if.forecast_bcf[data.what_if.shift_f.indexOf(s)];
    const [cold, mid, warm] = [at(-10), at(0), at(10)];
    const lesson = cold < mid - 3 && warm < mid - 3
      ? "At this time of year a turn either way cuts the injection: heat means more air conditioning, cold means the first heating."
      : cold < warm
        ? "Colder weather burns more gas for heating, so less goes into storage."
        : "Hotter weather burns more gas in power plants for air conditioning, so less goes into storage.";
    return { at, lesson };
  }, [data]);

  const whatIfOption = useMemo<Option | null>(() => {
    if (!data) return null;
    return {
      animation: false,
      grid: { left: 44, right: 12, top: 30, bottom: 44 },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => bcf(v) },
      xAxis: { type: "category", ...axisBase, data: data.what_if.shift_f.map((s) => (s > 0 ? `+${s}` : `${s}`)),
        ...xName("°F colder (−) or warmer (+) than forecast"),
        axisLabel: { ...axisBase.axisLabel, interval: 4 } },
      yAxis: { type: "value", ...valueAxisBase, scale: true, ...yName("Bcf into storage") },
      series: [{
        type: "line", smooth: 0.3, showSymbol: false, lineStyle: { color: GREEN, width: 1.6 },
        data: data.what_if.forecast_bcf,
        markPoint: { symbol: "circle", symbolSize: 9, itemStyle: { color: INK }, label: { show: false },
          data: [{ coord: [data.what_if.shift_f.indexOf(shift), data.what_if.forecast_bcf[data.what_if.shift_f.indexOf(shift)]] }] },
      }],
    };
  }, [data, shift]);

  const years = useMemo(() => (data ? data.history.week_ending.map((d) => +d.slice(0, 4)) : []), [data]);
  const minYear = years[0] ?? 2022;
  const maxYear = years.at(-1) ?? 2026;
  const [from, to] = range ?? [minYear, maxYear];

  const historyOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const idx = years.map((y, i) => (y >= from && y <= to ? i : -1)).filter((i) => i >= 0);
    const hs = data.history;
    const dates = idx.map((i) => hs.week_ending[i]);
    const label = (v: string) => (from === to ? day(v).slice(0, 6) : v.slice(0, 4));
    return {
      animationDuration: 700,
      grid: [{ left: 48, right: 12, top: narrow ? 84 : 56, height: narrow ? "46%" : "52%" }, { left: 48, right: 12, top: "76%", bottom: 28 }],
      legend: { top: 0, left: 0, itemGap: 18, textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 12, color: INK_SOFT } },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => (v == null ? "" : bcf(v)) },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      xAxis: [
        { type: "category", data: dates, ...axisBase, axisLabel: { show: false } },
        { type: "category", data: dates, gridIndex: 1, ...axisBase,
          axisLabel: { ...axisBase.axisLabel, formatter: label, interval: (i: number) =>
            i === 0 || (from === to ? dates[i].slice(5, 7) !== dates[i - 1].slice(5, 7) : dates[i].slice(0, 4) !== dates[i - 1].slice(0, 4)) } },
      ],
      yAxis: [
        { type: "value", ...valueAxisBase, ...yName("Bcf in (+) or out (−) of storage that week") },
        { type: "value", gridIndex: 1, ...valueAxisBase, ...yName("Model miss, Bcf"), splitNumber: 2 },
      ],
      series: [
        { name: "Reported by EIA", type: "line", showSymbol: false, lineStyle: { color: INK, width: 1.4 },
          itemStyle: { color: INK }, data: idx.map((i) => hs.actual[i]) },
        { name: "Five-year average guess", type: "line", showSymbol: false,
          lineStyle: { color: GUESS, width: 1.2, type: "dashed" }, itemStyle: { color: GUESS },
          data: idx.map((i) => hs.bench_5yr_avg[i]) },
        { name: "Model forecast", type: "line", showSymbol: false, lineStyle: { color: GREEN, width: 1.4 },
          itemStyle: { color: GREEN }, data: idx.map((i) => hs.blend[i]) },
        { name: "Model miss", type: "bar", xAxisIndex: 1, yAxisIndex: 1, barCategoryGap: "20%",
          itemStyle: { color: "rgba(79,122,58,0.55)" },
          data: idx.map((i) => {
            const miss = +(hs.blend[i] - hs.actual[i]).toFixed(1);
            return { value: miss, itemStyle: { color: Math.abs(miss) > 30 ? RED : "rgba(79,122,58,0.55)" } };
          }) },
      ],
    };
  }, [data, years, from, to, narrow]);

  const surpriseOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const g = data.surprise.groups;
    const labels = ["Much less gas than the model expected", "", "", "", "Much more gas than the model expected"];
    return {
      animationDuration: 800,
      grid: { left: 44, right: 8, top: 32, bottom: 56 },
      tooltip: { ...tooltipBase, trigger: "item",
        formatter: (p: { dataIndex: number; value: number }) =>
          `${g[p.dataIndex].weeks} reports<br/>average move ${p.value.toFixed(2)}%<br/>price up on ${pct(g[p.dataIndex].share_price_up)} of them` },
      xAxis: { type: "category", ...axisBase, data: g.map((_, i) => labels[i] || `${i + 1}`),
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: 11, width: 96,
          overflow: "break", interval: 0 } },
      yAxis: { type: "value", ...valueAxisBase, ...yName("Futures price move that day"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      series: [{
        type: "bar", barWidth: "55%",
        data: g.map((x) => ({ value: x.avg_move_report_day_pct,
          itemStyle: { color: x.avg_move_report_day_pct < -0.8 ? RED : x.avg_move_report_day_pct > 0.2 ? GREEN : SLATE } })),
        label: { show: true, position: "top", fontFamily: MONO, fontSize: 11, color: INK_SOFT,
          formatter: (p: { value: number }) => `${p.value > 0 ? "+" : ""}${p.value.toFixed(1)}%` },
      }],
    };
  }, [data]);

  // Average miss by year, from the same backtest (+ = forecast too high)
  const byYear = useMemo(() => {
    if (!data) return [];
    const out = new Map<number, { n: number; bias: number; abs: number }>();
    data.history.week_ending.forEach((d, i) => {
      const y = +d.slice(0, 4);
      const miss = data.history.blend[i] - data.history.actual[i];
      const r = out.get(y) ?? { n: 0, bias: 0, abs: 0 };
      out.set(y, { n: r.n + 1, bias: r.bias + miss, abs: r.abs + Math.abs(miss) });
    });
    return [...out].map(([year, r]) => ({ year, weeks: r.n, bias: r.bias / r.n, mae: r.abs / r.n }));
  }, [data]);

  const shifted = whatIf?.at(shift);
  const forecastShare = next?.forecast_weather_share ?? 0;
  const sa = data?.surprise;

  return (
    <Chapter
      id="forecast"
      number={5}
      accent={accent}
      meta={data?.meta}
      question="How much gas will Thursday’s storage report show?"
      answer={
        h && next && (
          <p>
            About <strong className="num text-ink">{bcf(next.forecast_bcf)}</strong> for the week ending{" "}
            {day(next.week_ending)}, reported on {day(next.report_date)}. Tested on {h.test_weeks} weeks since 2022,
            the model missed by <strong className="num text-ink">{h.model_miss_bcf.toFixed(1)} Bcf</strong> on
            average, less than half the {h.benchmark_miss_bcf.toFixed(0)} Bcf miss of the usual five-year-average
            guess.
          </p>
        )
      }
      notes={
        <>
          <Note term="Bcf">
            Billion cubic feet of gas. The US uses about 90 Bcf on an average day. “+” means gas went into storage,
            “−” means it came out.
          </Note>
          <Note term="What the model reads">
            Temperatures in 12 cities across the five storage regions, last week’s report, the time of year, holiday
            weeks, and LNG exports and production as far as they have been published.
          </Note>
          <Note term="A fair test">
            Each year from 2022 on is forecast by a model trained only on the years before it. Nothing it is scored
            on was seen in training.
          </Note>
        </>
      }
      why="The storage report is the one scheduled number every gas trader watches. A desk with its own estimate knows at 10:31 whether the number was really a surprise, and roughly how far the price should move, instead of reacting to the headline."
      details={
        data && (
          <div className="grid gap-10 md:grid-cols-2">
            <div>
              <h3 className="font-serif text-xl font-semibold">What the model learned</h3>
              <p className="mt-2 text-[0.95rem] text-ink-soft italic">
                Change in the weekly number for one more degree day in a region, all else equal
              </p>
              <table className="mt-3 w-full text-left text-[0.95rem]">
                <thead>
                  <tr className="border-b border-rule text-ink-faint">
                    <th className="py-2 pr-4 font-normal italic">Region</th>
                    <th className="py-2 pr-4 text-right font-normal italic">Heating degree day</th>
                    <th className="py-2 text-right font-normal italic">Cooling degree day</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.weather_effect).map(([region, e]) => (
                    <tr key={region} className="border-b border-rule/60 last:border-0">
                      <td className="py-2 pr-4">{region}</td>
                      <td className="num py-2 pr-4 text-right text-[0.85rem]">{bcf(e.heating, 2)}</td>
                      <td className="num py-2 text-right text-[0.85rem]">{bcf(e.cooling, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-4 text-[0.95rem] leading-relaxed text-ink-soft">
                A degree day is how far a day’s average temperature sits below 65°F (heating) or above it
                (cooling): a 50°F day counts 15. South Central weighs most because it holds the most gas-fired
                power and industry. Holiday weeks add gas to storage as offices and factories close: Thanksgiving{" "}
                {bcf(data.holidays.thanksgiving)}, Christmas {bcf(data.holidays.christmas)}, New Year{" "}
                {bcf(data.holidays.new_year)}.
              </p>
              <p className="mt-3 text-[0.95rem] leading-relaxed text-ink-soft">
                Production, LNG exports and the long-run trend all rose together since 2010, so the model cannot
                tell their separate effects apart. They help the forecast but their individual weights mean
                nothing, and they are left out here.
              </p>
            </div>
            <div>
              <h3 className="font-serif text-xl font-semibold">Year by year</h3>
              <p className="mt-2 text-[0.95rem] text-ink-soft italic">
                Average miss, and whether the model leaned too high (+) or too low (−)
              </p>
              <table className="mt-3 w-full text-left text-[0.95rem]">
                <thead>
                  <tr className="border-b border-rule text-ink-faint">
                    <th className="py-2 pr-4 font-normal italic">Year</th>
                    <th className="py-2 pr-4 text-right font-normal italic">Weeks</th>
                    <th className="py-2 pr-4 text-right font-normal italic">Average miss</th>
                    <th className="py-2 text-right font-normal italic">Lean</th>
                  </tr>
                </thead>
                <tbody>
                  {byYear.map((y) => (
                    <tr key={y.year} className="border-b border-rule/60 last:border-0">
                      <td className="num py-2 pr-4 text-[0.85rem]">{y.year}</td>
                      <td className="num py-2 pr-4 text-right text-[0.85rem]">{y.weeks}</td>
                      <td className="num py-2 pr-4 text-right text-[0.85rem]">{y.mae.toFixed(1)} Bcf</td>
                      <td className="num py-2 text-right text-[0.85rem]">{bcf(y.bias, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {byYear.filter((y) => Math.abs(y.bias) > 8).map((y) => (
                <p key={y.year} className="mt-4 text-[0.95rem] leading-relaxed text-ink-soft">
                  In {y.year} it leaned {y.bias < 0 ? "low" : "high"} by about {Math.abs(y.bias).toFixed(0)} Bcf a
                  week: more gas {y.bias < 0 ? "went into storage (or less came out)" : "came out of storage (or less went in)"}{" "}
                  than the weather alone explained.
                </p>
              ))}
              <p className="mt-4 text-[0.95rem] leading-relaxed text-ink-soft">
                The holiday and production inputs were added after looking at misses from 2022 on, so the test
                score is slightly flattering. The forecast log below is the clean test: every entry is saved
                before the report comes out.
              </p>
            </div>
          </div>
        )
      }
    >
      {data && h && next && whatIf && (
        <>
          <div className="grid gap-10 md:grid-cols-12">
            <div className="border-t border-ink/60 pt-4 md:col-span-5">
              <div className="flex items-start justify-between gap-4">
                <h3 className="font-serif text-xl font-semibold leading-snug">Next report</h3>
                <span className="stamp" style={{ color: accent }}>{day(next.report_date)}</span>
              </div>
              <p className="mt-2 text-[0.95rem] text-ink-soft italic">Week ending {day(next.week_ending)}</p>
              <p className="num mt-4 text-5xl font-semibold" style={{ color: accent }}>{bcf(next.forecast_bcf)}</p>
              <RangeBar low={next.low_bcf} high={next.high_bcf} value={next.forecast_bcf} accent={accent} />
              <p className="mt-3 text-[0.95rem] leading-relaxed text-ink-soft">
                Likely between <strong className="num text-ink">{next.low_bcf.toFixed(0)}</strong> and{" "}
                <strong className="num text-ink">{next.high_bcf.toFixed(0)} Bcf</strong>: the model’s past misses
                would have put 8 of every 10 weeks inside a range this wide.
                {forecastShare > 0 && ` ${pct(forecastShare)} of this week’s weather is still a forecast.`}
              </p>
              <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-rule pt-4 text-[0.95rem]">
                <div>
                  <dt className="text-ink-faint">Last report</dt>
                  <dd className="num">{bcf(h.last_change_bcf)}</dd>
                </div>
                <div>
                  <dt className="text-ink-faint">Gas in storage</dt>
                  <dd className="num">{h.last_storage_bcf.toLocaleString("en-US")} Bcf</dd>
                </div>
                {projection && (
                  <div className="col-span-2">
                    <dt className="text-ink-faint">The week after ({day(projection.report_date)})</dt>
                    <dd>
                      <span className="num">about {bcf(projection.forecast_bcf)}</span>
                      <span className="text-ink-faint"> · rougher: built on this forecast and forecast weather only</span>
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            <div className="border-t border-ink/60 pt-4 md:col-span-7">
              <h3 className="font-serif text-xl font-semibold leading-snug">What if the rest of the week turns warmer or colder?</h3>
              {forecastShare > 0 ? (
                <>
                  <p className="mt-2 text-[0.95rem] text-ink-soft italic">
                    Only the days still forecast are moved. The days already past stay as measured.
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-4">
                    <input type="range" min={-10} max={10} step={1} value={shift} aria-label="Degrees warmer or colder than forecast"
                      onChange={(e) => setShift(+e.target.value)} className="w-56" style={{ accentColor: accent }} />
                    <p className="text-[0.95rem]">
                      <span className="num">{shift === 0 ? "As forecast" : `${Math.abs(shift)}°F ${shift < 0 ? "colder" : "warmer"}`}</span>
                      <span className="text-ink-faint"> → </span>
                      <strong className="num">{shifted != null && bcf(shifted)}</strong>
                      {shift !== 0 && shifted != null && (
                        <span className="num text-ink-faint"> ({(shifted - next.forecast_bcf) >= 0 ? "+" : "−"}
                          {Math.abs(shifted - next.forecast_bcf).toFixed(0)} vs forecast)</span>
                      )}
                    </p>
                  </div>
                  <div className="mt-2">
                    {whatIfOption && <EChart option={whatIfOption} height={220} merge ariaLabel="Forecast storage change for warmer or colder weather" />}
                  </div>
                  <p className="mt-1 text-[0.95rem] text-ink-soft">{whatIf.lesson} Wiggles of a Bcf or two are the model’s own rounding, not weather.</p>
                </>
              ) : (
                <p className="mt-2 text-[0.95rem] text-ink-soft">The whole week has already happened, so there is no weather left to change.</p>
              )}
            </div>
          </div>

          <div className="mt-14">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h3 className="font-serif text-xl font-semibold">Every week since 2022</h3>
                <p className="mt-2 text-[0.95rem] text-ink-soft italic">
                  What EIA reported, the model’s forecast, and the five-year average guess. Red bars are misses over 30 Bcf.
                </p>
              </div>
              <YearRange min={minYear} max={maxYear} from={from} to={to} onChange={(a, b) => setRange([a, b])} />
            </div>
            <div className="mt-4 border-y border-rule">
              {historyOption && <EChart option={historyOption} height={420} ariaLabel="Weekly storage change: reported, model forecast and five-year average" />}
            </div>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-[0.95rem]">
              <thead>
                <tr className="border-b border-rule text-ink-faint">
                  <th className="py-2 pr-4 font-normal italic">Forecast method, {h.test_weeks} weeks from 2022</th>
                  <th className="py-2 pr-4 text-right font-normal italic">Average miss</th>
                  <th className="py-2 pr-4 text-right font-normal italic">Within 10 Bcf</th>
                  <th className="py-2 pr-4 text-right font-normal italic">Winter miss</th>
                  <th className="py-2 pr-4 text-right font-normal italic">Summer miss</th>
                  <th className="py-2 text-right font-normal italic">Worst miss</th>
                </tr>
              </thead>
              <tbody>
                {data.scores.map((s) => {
                  const mine = s.model === "blend";
                  return (
                    <tr key={s.model} className={`border-b border-rule/60 last:border-0 ${mine ? "font-semibold" : ""}`}>
                      <td className="py-2.5 pr-4" style={mine ? { color: accent } : undefined}>{MODEL_NAMES[s.model] ?? s.model}</td>
                      <td className="num py-2.5 pr-4 text-right text-[0.85rem]">{s.mae_bcf.toFixed(1)} Bcf</td>
                      <td className="num py-2.5 pr-4 text-right text-[0.85rem]">{pct(s.share_within_10bcf)} of weeks</td>
                      <td className="num py-2.5 pr-4 text-right text-[0.85rem]">{s.mae_winter_bcf.toFixed(1)}</td>
                      <td className="num py-2.5 pr-4 text-right text-[0.85rem]">{s.mae_summer_bcf.toFixed(1)}</td>
                      <td className="num py-2.5 text-right text-[0.85rem]">{s.worst_miss_bcf.toFixed(0)} <span className="text-ink-faint">({day(s.worst_miss_week)})</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="mt-2 text-[0.9rem] text-ink-faint">
              Winter is November to March, when weather swings the number most and the simple guesses miss by 50 Bcf or more.
            </p>
          </div>

          {sa && surpriseOption && (
            <div className="mt-14 grid gap-10 md:grid-cols-12">
              <div className="border-t border-ink/60 pt-4 md:col-span-7">
                <div className="flex items-start justify-between gap-4">
                  <h3 className="font-serif text-xl font-semibold leading-snug">Does a surprise against the model move the price?</h3>
                  <span className="stamp text-watch">Clearer before 2022</span>
                </div>
                <p className="mt-2 text-[0.95rem] text-ink-soft italic">
                  Average futures move on report day, {sa.all.weeks} reports since 2016 in five groups by how far the
                  number landed from the model
                </p>
                <div className="mt-3">
                  <EChart option={surpriseOption} height={270} ariaLabel="Price move by surprise against the model" />
                </div>
              </div>
              <div className="space-y-4 border-t border-ink/60 pt-4 text-[0.98rem] leading-relaxed text-ink-soft md:col-span-5">
                <p>
                  The price fell about <strong className="num text-ink">{Math.abs(sa.all.pct_per_10bcf).toFixed(2)}%</strong> for
                  every 10 Bcf more gas than the model expected. That is about{" "}
                  {Math.round(sa.all.pct_per_10bcf / sa.simple.pct_per_10bcf)} times the effect of the simple measure in
                  chapter 4, on the same weeks.
                </p>
                <p>
                  Almost all of it comes from 2016 to 2021 ({signedPct(sa.early.pct_per_10bcf)} per 10 Bcf). Since 2022
                  it is {signedPct(sa.recent.pct_per_10bcf)}, small enough to be chance. Daily price swings have been
                  much bigger since 2022, which can hide a small effect, and the analyst forecasts traders really use
                  may simply have got better.
                </p>
                <p className="text-[0.9rem] text-ink-faint">
                  Forecasts for 2016 to 2021 come from the same walk-forward test, but those years were also used to
                  choose the model’s settings.
                </p>
              </div>
            </div>
          )}

          <div className="mt-14">
            <h3 className="font-serif text-xl font-semibold">Forecast log</h3>
            <p className="mt-2 text-[0.95rem] text-ink-soft italic">
              Every forecast is written down before the report comes out and scored once it does. The dates are
              checkable in the project’s history.
            </p>
            <div className="mt-4 overflow-x-auto border-y border-rule">
              <table className="w-full min-w-[600px] text-left text-[0.95rem]">
                <thead>
                  <tr className="border-b border-rule text-ink-faint">
                    <th className="py-2 pr-4 font-normal italic">Made on</th>
                    <th className="py-2 pr-4 font-normal italic">Report</th>
                    <th className="py-2 pr-4 text-right font-normal italic">Forecast</th>
                    <th className="py-2 pr-4 text-right font-normal italic">Likely range</th>
                    <th className="py-2 pr-4 text-right font-normal italic">Reported</th>
                    <th className="py-2 text-right font-normal italic">Miss</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.log].reverse().map((r) => (
                    <tr key={`${r.made_on}-${r.week_ending}`} className="border-b border-rule/60 last:border-0">
                      <td className="num py-2.5 pr-4 text-[0.85rem] text-ink-soft">{day(r.made_on)}</td>
                      <td className="py-2.5 pr-4">
                        {day(r.report_date)}
                        {r.kind === "projection" && <span className="text-ink-faint"> (two weeks ahead)</span>}
                      </td>
                      <td className="num py-2.5 pr-4 text-right text-[0.85rem]">{bcf(r.forecast_bcf)}</td>
                      <td className="num py-2.5 pr-4 text-right text-[0.85rem] text-ink-soft">{r.low_bcf.toFixed(0)} to {r.high_bcf.toFixed(0)}</td>
                      <td className="num py-2.5 pr-4 text-right text-[0.85rem]">{r.actual_bcf == null ? <span className="text-ink-faint">waiting</span> : bcf(r.actual_bcf)}</td>
                      <td className="num py-2.5 text-right text-[0.85rem]">{r.miss_bcf == null ? "" : `${r.miss_bcf > 0 ? "+" : r.miss_bcf < 0 ? "−" : ""}${Math.abs(r.miss_bcf).toFixed(0)}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </Chapter>
  );
}

