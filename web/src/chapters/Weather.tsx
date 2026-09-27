import { useMemo } from "react";

import { Chapter } from "../components/Chapter";
import { EChart, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, yName, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";
import { day } from "../lib/format";

interface Spike {
  start: string;
  peak_day: string;
  peak_price: number;
  price_before: number;
  warned_by_weather: boolean;
  cold_season: boolean;
  forecast_covered: boolean;
  forecast_notice_days: number | null;
}

interface ForecastDay {
  date: string;
  level: string;
  midland_low_f: number;
  houston_low_f: number;
  max_gulf_gust_mph: number;
}

interface StormWatch extends DataFile<{
  spike_events: number;
  cold_season_spikes: number;
  warned_perfect_forecast: number;
  spikes_with_archived_forecasts: number;
  warned_real_forecasts: number;
  warning_episodes: number;
  false_alarms: number;
}> {
  spikes: Spike[];
  forecast: ForecastDay[];
}

// Names only where the cause is documented (the Oct 2020 spike matches 89 mph gusts at Henry Hub that day)
const SPIKE_NAME: Record<string, string> = {
  "2018-01": "January 2018 cold snap",
  "2020-10": "Hurricane Delta",
  "2021-02": "Winter Storm Uri",
  "2024-01": "Jan 2024 arctic blast",
  "2025-01": "Jan 2025 cold snap",
  "2026-01": "Winter Storm Fern",
};

function spikeName(s: Spike) {
  return SPIKE_NAME[s.start.slice(0, 7)] ?? (s.cold_season ? "Cold-season spike" : "Spike");
}

function Mark({ ok, children }: { ok: boolean | null; children: React.ReactNode }) {
  if (ok === null) return <span className="text-ink-faint">{children}</span>;
  return <span className={ok ? "text-good" : "text-act"}>{children}</span>;
}

export function Weather() {
  const data = useData<StormWatch>("storm_watch");
  const accent = accentOf("weather");

  const forecastOption = useMemo<Option | null>(() => {
    if (!data) return null;
    const f = data.forecast;
    const line = (color: string) => ({ color, width: 1.6 });
    const threshold = (y: number, text: string, color: string) => ({
      yAxis: y, lineStyle: { color, type: "dashed" as const, width: 1 },
      label: { formatter: text, color, fontFamily: MONO, fontSize: 10, position: "insideEndTop" as const },
    });
    return {
      animationDuration: 800,
      grid: { left: 40, right: 12, top: 64, bottom: 28 },
      legend: { top: 0, left: 0, itemGap: 22, textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => `${v.toFixed(0)}°F` },
      xAxis: { type: "category", data: f.map((d) => d.date), ...axisBase,
        axisLabel: { ...axisBase.axisLabel, formatter: (v: string) => day(v).replace(/, \d{4}$/, "") } },
      yAxis: { type: "value", min: 0, ...valueAxisBase, ...yName("Overnight low, °F"),
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}°" } },
      series: [
        { name: "Midland, Permian gas fields", type: "line", symbol: "none", lineStyle: line("#b85a17"),
          itemStyle: { color: "#b85a17" },
          data: f.map((d) => d.midland_low_f),
          markLine: { symbol: "none", silent: true, data: [threshold(10, "Midland warning 10°F", "#b0352a")] } },
        { name: "Houston", type: "line", symbol: "none", lineStyle: line("#2f5d8c"),
          itemStyle: { color: "#2f5d8c" },
          data: f.map((d) => d.houston_low_f),
          markLine: { symbol: "none", silent: true, data: [threshold(25, "Houston warning 25°F", "#b0352a")] } },
      ],
    };
  }, [data]);

  const h = data?.headline;
  const alertDays = data?.forecast.filter((d) => d.level !== "none").length ?? 0;

  return (
    <Chapter
      id="weather"
      number={6}
      accent={accent}
      meta={data?.meta}
      question="Can the weather forecast warn a desk before a price spike?"
      answer={
        h && (
          <p>
            Sometimes. Severe cold came within a week of{" "}
            <strong className="num text-ink">{h.warned_perfect_forecast} of {h.cold_season_spikes}</strong> winter
            spikes, so weather clearly drives them. But prices move on the forecast, days before the cold arrives. With
            the forecasts people actually had, the alert caught{" "}
            <strong className="num text-ink">{h.warned_real_forecasts} of {h.spikes_with_archived_forecasts}</strong>{" "}
            recent spikes, and{" "}
            <strong className="num text-act">{h.false_alarms} of {h.warning_episodes}</strong> warnings came to nothing.
          </p>
        )
      }
      notes={
        <>
          <Note term="The alert">
            Warning if Midland, in the Permian gas fields, is forecast at 10°F or colder, or Houston at 25°F or
            colder, or Gulf Coast gusts reach 74 mph. Set before looking at any results.
          </Note>
          <Note term="Why Midland">
            In hard freezes, wells there freeze up and stop producing, so supply drops just as demand jumps.
          </Note>
        </>
      }
      why="A simple temperature rule is a useful reminder to check the book, not a price forecast. The desk still has to decide; the alert just gives it a few days’ notice some of the time."
    >
      <p className="text-[0.95rem] text-ink-soft italic">
        Every Henry Hub price spike since 2010, and what the weather said
      </p>
      <div className="mt-4 overflow-x-auto border-y border-rule">
        <table className="w-full min-w-[640px] text-left text-[0.95rem]">
          <thead>
            <tr className="border-b border-rule text-ink-faint">
              <th className="py-2 pr-4 font-normal italic">Spike</th>
              <th className="py-2 pr-4 font-normal italic">Started</th>
              <th className="py-2 pr-4 text-right font-normal italic">Price before → peak</th>
              <th className="py-2 pr-4 font-normal italic">Severe weather that week</th>
              <th className="py-2 font-normal italic">Real forecast warned</th>
            </tr>
          </thead>
          <tbody>
            {data?.spikes.map((s) => (
              <tr key={s.start} className="border-b border-rule/60 last:border-0">
                <td className="py-2.5 pr-4 font-semibold">{spikeName(s)}</td>
                <td className="num py-2.5 pr-4 text-[0.85rem] text-ink-soft">{day(s.start)}</td>
                <td className="num py-2.5 pr-4 text-right text-[0.85rem]">
                  ${s.price_before.toFixed(2)} → <strong>${s.peak_price.toFixed(2)}</strong>
                </td>
                <td className="py-2.5 pr-4">
                  <Mark ok={s.warned_by_weather}>{s.warned_by_weather ? "Yes" : "No"}</Mark>
                </td>
                <td className="py-2.5">
                  {!s.forecast_covered ? (
                    <Mark ok={null}>Before forecast archive</Mark>
                  ) : s.forecast_notice_days !== null ? (
                    <Mark ok>{`Yes, ${s.forecast_notice_days} days ahead`}</Mark>
                  ) : (
                    <Mark ok={false}>No</Mark>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-12">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <h3 className="font-serif text-xl font-semibold">Right now</h3>
          {data && (
            <span className={`stamp ${alertDays ? "text-act" : "text-good"}`}>
              {alertDays ? `${alertDays} alert days` : "No alert"}
            </span>
          )}
        </div>
        <p className="mt-2 text-[0.95rem] text-ink-soft italic">
          Forecast overnight lows for the next 16 days, with the warning lines
        </p>
        <div className="mt-3 border-y border-rule">
          {forecastOption && <EChart option={forecastOption} height={260} ariaLabel="16-day forecast lows for Midland and Houston" />}
        </div>
      </div>
    </Chapter>
  );
}
