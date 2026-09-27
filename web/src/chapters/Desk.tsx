import { useMemo, useState } from "react";

import { Chapter } from "../components/Chapter";
import { EChart, INK_SOFT, MONO, axisBase, tooltipBase, valueAxisBase, type Option } from "../components/EChart";
import { Note } from "../components/Note";
import { accentOf } from "../lib/chapters";
import { useData, type DataFile } from "../lib/data";
import { day, money, pct } from "../lib/format";
import { useNarrow } from "../lib/useNarrow";

const PURPLE = "#7a4e8c";
const GOOD = "#3c8d5a";
const WATCH = "#b98311";
const ACT = "#b0352a";
const FAINT = "#b9c3cf";
const FERN: [string, string] = ["2026-01-20", "2026-01-30"];
const statusColor = (u: number) => (u >= 1 ? ACT : u >= 0.75 ? WATCH : GOOD);

interface Book extends DataFile<{ book_value: number; margin_captured: number; margin_share: number }> {
  daily: { date: string[]; mtm_total: number[]; pnl: (number | null)[]; new_deals: (number | null)[];
    forward_price_move: (number | null)[]; delivery_and_spot: (number | null)[] };
}

interface Credit extends DataFile<{
  storm_week_name: string; storm_week_day: string; storm_week_utilization: number; storm_week_before: number;
  payment_lag_name: string; payment_lag_day: string; payment_lag_utilization: number; payment_lag_owed: number;
  payment_lag_before: number; default_name: string; default_day: string; default_loss: number;
  loss_without_setoff: number;
}> {
  utilization: Record<string, (string | number | null)[]>;
  default: { name: string; default_date: string; unpaid_purchases: number; future_value: number; loss: number;
    loss_without_setoff: number; open_deals: number; spot_on_default_date: number }[];
}

interface Stress extends DataFile {
  summary: { storm: string; peak_spot_multiple: number; worst_pnl: number; newly_over_limit: string }[];
  credit: { storm: string; name: string; base_utilization: number; peak_utilization: number; alert: string }[];
}

interface Matching extends DataFile<{ planted: number; raised: number; on_exact_trade: number; false_alarms: number }> {
  by_issue: { issue: string; count: number }[];
}

/* ---------- 6. Where the money comes from ---------- */

function BookSection() {
  const book = useData<Book>("book");
  const accent = accentOf("desk");
  const narrow = useNarrow();

  const option = useMemo<Option | null>(() => {
    if (!book) return null;
    const d = book.daily;
    let margin = 0;
    let market = 0;
    const m: number[] = [];
    const k: number[] = [];
    d.date.forEach((_, i) => {
      margin += d.new_deals[i] ?? 0;
      market += (d.forward_price_move[i] ?? 0) + (d.delivery_and_spot[i] ?? 0);
      m.push(Math.round(margin));
      k.push(Math.round(market));
    });
    return {
      animationDuration: 1000,
      grid: { left: 52, right: 16, top: narrow ? 64 : 40, bottom: 28 },
      legend: { top: 0, left: 0, textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => money(v) },
      xAxis: { type: "category", data: d.date, ...axisBase,
        axisLabel: { ...axisBase.axisLabel, formatter: (v: string) => v.slice(0, 7) } },
      yAxis: { type: "value", ...valueAxisBase, axisLabel: { ...valueAxisBase.axisLabel, formatter: (v: number) => money(v, 0) } },
      series: [
        { name: "Margin locked in on new deals", type: "line", showSymbol: false, lineStyle: { color: PURPLE, width: 2 },
          itemStyle: { color: PURPLE },
          areaStyle: { color: "rgba(122,78,140,0.10)" }, data: m },
        { name: "Gains and losses from price moves", type: "line", showSymbol: false, lineStyle: { color: "#8b97a6", width: 2 },
          itemStyle: { color: "#8b97a6" },
          data: k,
          markArea: { silent: true, itemStyle: { color: "rgba(184,90,23,0.12)" },
            label: { show: true, formatter: "Fern", color: "#b85a17", fontFamily: MONO, fontSize: 10, position: "insideTop" },
            data: [[{ xAxis: FERN[0] }, { xAxis: FERN[1] }]] } },
      ],
    };
  }, [book, narrow]);

  const explain = useMemo<Option | null>(() => {
    if (!book) return null;
    const d = book.daily;
    const idx = d.date.map((x, i) => (x >= "2026-01-12" && x <= "2026-02-13" ? i : -1)).filter((i) => i >= 0);
    const series = (name: string, key: keyof Book["daily"], color: string) => ({
      name, type: "bar", stack: "pnl", itemStyle: { color },
      data: idx.map((i) => (d[key] as (number | null)[])[i]),
    });
    return {
      animationDuration: 800,
      grid: { left: 52, right: 12, top: narrow ? 64 : 40, bottom: 44 },
      legend: { top: 0, left: 0, textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, axisPointer: { type: "shadow" }, valueFormatter: (v: number) => money(v) },
      xAxis: { type: "category", data: idx.map((i) => day(d.date[i]).replace(/, \d{4}$/, "")), ...axisBase,
        axisLabel: { ...axisBase.axisLabel, rotate: 45 } },
      yAxis: { type: "value", ...valueAxisBase, axisLabel: { ...valueAxisBase.axisLabel, formatter: (v: number) => money(v, 0) } },
      series: [
        series("New deals", "new_deals", PURPLE),
        series("Forward price move", "forward_price_move", "#2f5d8c"),
        series("Delivery and spot", "delivery_and_spot", "#b85a17"),
      ],
    };
  }, [book, narrow]);

  const h = book?.headline;
  return (
    <Chapter
      id="desk"
      number={6}
      accent={accent}
      meta={book?.meta}
      question="Where does the desk’s money actually come from?"
      answer={
        h && (
          <p>
            Mostly from the margin, not from betting on price. Of the book’s{" "}
            <strong className="num text-ink">{money(h.book_value)}</strong> value,{" "}
            <strong className="num text-desk">{money(h.margin_captured)}</strong> ({pct(h.margin_share)}) is the few cents
            the desk locks in on every deal. A position limit keeps it from betting big either way.
          </p>
        )
      }
      notes={
        <>
          <Note term="The simulated desk">
            877 made-up trades at Henry Hub, January 2025 to September 2026, with eight fictional counterparties. Every
            price is real.
          </Note>
          <Note term="Position limit">
            A rule that the desk can’t be more than 25,000 MMBtu a day short or long in any month.
          </Note>
        </>
      }
      why="Owners and lenders want to see steady margin, not lucky bets. If most of the value came from price moves, one bad winter could take it all back."
      details={
        explain && (
          <div>
            <p className="text-[0.95rem] text-ink-soft italic">
              Daily profit around Winter Storm Fern, split by cause: new deals, the forward price, and gas already
              flowing
            </p>
            <div className="mt-4 border-y border-rule">
              <EChart option={explain} height={320} ariaLabel="Daily profit and loss explained around Winter Storm Fern" />
            </div>
          </div>
        )
      }
    >
      <div className="mb-10 border-l-4 border-desk/40 simulated-stripes py-3 pr-3 pl-4 text-[0.98rem] text-ink-soft">
        From here on the trades, customers and suppliers are simulated, because real trading books are confidential.
        The prices they are valued at are real. The simulation is cleaner than real life: no cancelled deals and
        perfect deliveries, so read these results as a best case.
      </div>
      <p className="text-[0.95rem] text-ink-soft italic">Running total of where the book’s value came from</p>
      <div className="mt-4 border-y border-rule">
        {option && <EChart option={option} height={320} ariaLabel="Cumulative margin versus market gains" />}
      </div>
    </Chapter>
  );
}

/* ---------- 6b. Credit ---------- */

function Settlement({ d }: { d: Credit["default"][number] }) {
  const row = "flex justify-between gap-6 py-1.5";
  return (
    <div className="border border-ink/25 bg-white/60 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-semibold">Termination statement</p>
          <p className="text-[0.9rem] text-ink-soft">
            {d.name} stops delivering, {day(d.default_date)} (spot ${d.spot_on_default_date.toFixed(2)})
          </p>
        </div>
        <span className="stamp text-good">Loss $0</span>
      </div>
      <div className="num mt-4 border-t border-rule pt-2 text-[0.88rem]">
        <div className={row}><span>Cost to replace their gas at storm prices</span><span>{money(d.future_value, 2)}</span></div>
        <div className={row}><span>Less: what we still owed them (set-off)</span><span className="whitespace-nowrap">−{money(d.unpaid_purchases, 2)}</span></div>
        <div className={`${row} border-t border-ink/40 font-semibold`}><span>Our loss</span><span>{money(d.loss, 2)}</span></div>
        <div className={`${row} text-act`}><span>Loss if the contract had no set-off</span><span>{money(d.loss_without_setoff, 2)}</span></div>
      </div>
    </div>
  );
}

function CreditSection() {
  const credit = useData<Credit>("credit");
  const accent = accentOf("desk");
  const names = useMemo(() => (credit ? Object.keys(credit.utilization).filter((k) => k !== "date") : []), [credit]);
  const [picked, setPicked] = useState<string | null>(null);
  const name = picked ?? credit?.headline.payment_lag_name ?? "";

  const option = useMemo<Option | null>(() => {
    if (!credit || !name) return null;
    const dates = credit.utilization.date as string[];
    const values = (credit.utilization[name] as number[]).map((v) => (v == null ? null : Math.round(v * 1000) / 10));
    const top = Math.max(120, ...values.filter((v): v is number => v != null)) * 1.05;
    return {
      animationDuration: 700,
      grid: { left: 48, right: 16, top: 16, bottom: 28 },
      tooltip: { ...tooltipBase, valueFormatter: (v: number) => `${v.toFixed(0)}% of limit` },
      xAxis: { type: "category", data: dates, ...axisBase,
        axisLabel: { ...axisBase.axisLabel, formatter: (v: string) => v.slice(0, 7) } },
      yAxis: { type: "value", max: Math.ceil(top / 50) * 50, ...valueAxisBase,
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      series: [{
        type: "line", showSymbol: false, lineStyle: { color: PURPLE, width: 1.8 }, data: values,
        markArea: {
          silent: true,
          data: [
            [{ yAxis: 0, itemStyle: { color: "rgba(60,141,90,0.07)" } }, { yAxis: 75 }],
            [{ yAxis: 75, itemStyle: { color: "rgba(185,131,17,0.10)" } }, { yAxis: 100 }],
            [{ yAxis: 100, itemStyle: { color: "rgba(176,53,42,0.08)" } }, { yAxis: 10000 }],
            [{ xAxis: FERN[0], itemStyle: { color: "rgba(184,90,23,0.14)" } }, { xAxis: FERN[1] }],
          ],
        },
        markLine: { symbol: "none", silent: true, lineStyle: { color: ACT, type: "dashed" },
          label: { formatter: "limit", color: ACT, fontFamily: MONO, fontSize: 10, position: "insideEndTop" },
          data: [{ yAxis: 100 }] },
      }],
    };
  }, [credit, name]);

  const h = credit?.headline;
  return (
    <Chapter
      id="desk-credit"
      number="6b"
      accent={accent}
      meta={credit?.meta}
      question="Who owes us money, and when does it get dangerous?"
      answer={
        h && (
          <p>
            A month after the storm, not during it. January’s gas was billed at storm prices and isn’t paid until the
            25th of February. {h.payment_lag_name} went from{" "}
            <strong className="num text-ink">{pct(h.payment_lag_before)}</strong> of its credit limit before Winter
            Storm Fern to <strong className="num text-act">{pct(h.payment_lag_utilization)}</strong> on{" "}
            {day(h.payment_lag_day)}, owing <strong className="num text-ink">{money(h.payment_lag_owed)}</strong>.
          </p>
        )
      }
      notes={
        <>
          <Note term="Credit limit">
            The most a customer is allowed to owe us. Amber from 75%, red over 100%.
          </Note>
          <Note term="NAESB contract">
            The standard US gas contract. Gas delivered in one month is paid for on the 25th of the next, so up to
            about 55 days of gas can be owed at once.
          </Note>
          <Note term="Set-off">
            If a counterparty fails, what we owe them can be kept against what they owe us.
          </Note>
        </>
      }
      why="A desk that relaxes when the weather clears misses the most dangerous day. Ask for collateral before storm bills fall due, and check suppliers as well as customers."
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <p className="text-[0.95rem] text-ink-soft italic">Credit limit used, every trading day. Storm shaded.</p>
        <label className="flex items-center gap-2 text-[0.95rem]">
          <span className="text-ink-faint">Counterparty</span>
          <select className="rounded border border-ink/25 bg-transparent px-2 py-1" value={name}
            onChange={(e) => setPicked(e.target.value)}>
            {names.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>
      <div className="mt-4 border-y border-rule">
        {option && <EChart option={option} height={320} ariaLabel={`Credit limit used by ${name}`} />}
      </div>
      <div className="mt-10 grid gap-8 md:grid-cols-12">
        <div className="md:col-span-7">{credit?.default[0] && <Settlement d={credit.default[0]} />}</div>
        <div className="text-[0.98rem] leading-relaxed text-ink-soft md:col-span-5">
          <p className="font-semibold text-ink">When a supplier fails in a storm</p>
          <p className="mt-2">
            We had bought gas at fixed prices from this producer. When it stopped delivering mid-storm, replacing that
            gas cost far more. But we still owed it for gas it had already delivered, and the contract let us keep that
            money. Without that clause the desk would have lost {h && money(h.loss_without_setoff, 2)}.
          </p>
        </div>
      </div>
    </Chapter>
  );
}

/* ---------- 6c. Storm test ---------- */

function StormSection() {
  const stress = useData<Stress>("stress");
  const accent = accentOf("desk");
  const narrow = useNarrow();
  const storms = useMemo(() => stress?.summary.map((s) => s.storm) ?? [], [stress]);
  const [picked, setPicked] = useState<string | null>(null);
  const storm = picked ?? storms[0] ?? "";

  const option = useMemo<Option | null>(() => {
    if (!stress || !storm) return null;
    const rows = stress.credit.filter((r) => r.storm === storm).sort((a, b) => b.peak_utilization - a.peak_utilization);
    return {
      animationDuration: 600,
      grid: { left: 8, right: 48, top: narrow ? 64 : 48, bottom: 28, containLabel: true },
      legend: { top: 0, left: 0, textStyle: { fontFamily: "Source Serif 4, serif", fontSize: 13, color: INK_SOFT } },
      tooltip: { ...tooltipBase, axisPointer: { type: "shadow" }, valueFormatter: (v: number) => `${v}% of limit` },
      xAxis: { type: "value", splitNumber: narrow ? 3 : 6, ...valueAxisBase,
        axisLabel: { ...valueAxisBase.axisLabel, formatter: "{value}%" } },
      yAxis: { type: "category", inverse: true, ...axisBase,
        data: rows.map((r) => (r.alert === "defaulted" ? `${r.name} (defaulted)` : r.name)),
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: narrow ? 11 : 13,
          width: narrow ? 110 : 200, overflow: "break" } },
      series: [
        { name: "Today", type: "bar", barGap: "10%", itemStyle: { color: FAINT },
          data: rows.map((r) => Math.round(r.base_utilization * 100)) },
        { name: narrow ? "At the storm’s peak" : "At the storm’s peak (green / amber / red by limit used)", type: "bar",
          itemStyle: { color: "#465261" },
          data: rows.map((r) => ({ value: Math.round(r.peak_utilization * 100),
            itemStyle: { color: statusColor(r.peak_utilization) } })),
          label: { show: true, position: "right", fontFamily: MONO, fontSize: 11, color: INK_SOFT, formatter: "{c}%" },
          markLine: { symbol: "none", silent: true, lineStyle: { color: ACT, type: "dashed" },
            label: { formatter: "limit", color: ACT, fontFamily: MONO, fontSize: 10, position: "start" },
            data: [{ xAxis: 100 }] } },
      ],
    };
  }, [stress, storm, narrow]);

  const s = stress?.summary.find((x) => x.storm === storm);
  const newly = s && s.newly_over_limit !== "none" ? s.newly_over_limit : null;

  return (
    <Chapter
      id="desk-storms"
      number="6c"
      accent={accent}
      meta={stress?.meta}
      question="What if one of those storms hit today’s book?"
      answer={
        <p>
          The profit barely moves, because the position limit keeps the book close to flat. The damage shows up in
          credit: in a replay of Winter Storm Uri, a supplier we bought fixed-price gas from jumps from nothing owed to
          several times its limit, because its gas is suddenly worth far more than we agreed to pay.
        </p>
      }
      notes={
        <Note term="How the replay works">
          Each storm’s real day-by-day price moves are applied to today’s prices and today’s trades. It is a what-if,
          not a forecast.
        </Note>
      }
      why="Storm tests show the losses the daily risk number misses, and they point at the counterparty to call first."
    >
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Storm">
        {storms.map((name) => (
          <button key={name} type="button" role="radio" aria-checked={name === storm} onClick={() => setPicked(name)}
            className="rounded border px-3 py-1 text-[0.92rem] transition-colors"
            style={name === storm ? { background: PURPLE, borderColor: PURPLE, color: "#f8f4ea" }
              : { borderColor: "rgba(29,39,51,0.25)", color: "var(--color-ink-soft)" }}>
            {name}
          </button>
        ))}
      </div>
      {s && (
        <p className="mt-5 text-[1.02rem] text-ink-soft">
          Spot price up to <strong className="num text-ink">{s.peak_spot_multiple.toFixed(1)}×</strong> today’s level.
          Worst day for the book: <strong className="num text-ink">{money(s.worst_pnl)}</strong>.{" "}
          {newly ? <>Newly over the limit: <span className="font-semibold text-act">{newly}</span>.</> : "Nobody new goes over the limit."}
        </p>
      )}
      <div className="mt-4 border-y border-rule">
        {option && <EChart option={option} height={360} ariaLabel={`Credit limit used today and at the peak of ${storm}`} />}
      </div>
    </Chapter>
  );
}

/* ---------- 6d. Trade matching ---------- */

function MatchingSection() {
  const m = useData<Matching>("matching");
  const accent = accentOf("desk");
  const narrow = useNarrow();

  const option = useMemo<Option | null>(() => {
    if (!m) return null;
    const rows = [...m.by_issue].sort((a, b) => b.count - a.count);
    return {
      animationDuration: 700,
      grid: { left: 8, right: 40, top: 8, bottom: 24, containLabel: true },
      xAxis: { type: "value", minInterval: 5, ...valueAxisBase,
        axisLabel: { ...valueAxisBase.axisLabel, show: !narrow } },
      yAxis: { type: "category", inverse: true, data: rows.map((r) => r.issue), ...axisBase,
        axisLabel: { ...axisBase.axisLabel, fontFamily: "Source Serif 4, serif", fontSize: 13 } },
      series: [{ type: "bar", barWidth: "55%", itemStyle: { color: PURPLE }, data: rows.map((r) => r.count),
        label: { show: true, position: "right", fontFamily: MONO, fontSize: 11, color: INK_SOFT } }],
    };
  }, [m, narrow]);

  const h = m?.headline;
  return (
    <Chapter
      id="desk-matching"
      number="6d"
      accent={accent}
      meta={m?.meta}
      question="Did we book every trade the way the other side did?"
      answer={
        h && (
          <p>
            We planted <strong className="num text-ink">{h.planted}</strong> errors in the counterparties’ confirmations.
            The matcher flagged all <strong className="num text-good">{h.raised}</strong>, with{" "}
            <strong className="num text-ink">{h.false_alarms}</strong> false alarms. Two landed on an identical twin
            trade: same day, same customer, same price, so no system could tell them apart without a shared deal ID.
          </p>
        )
      }
      notes={
        <Note term="Confirmation">
          The other side’s written record of a trade. Checking every one against our own booking is the first job of
          a desk analyst each morning.
        </Note>
      }
      why="One wrong volume or price flows straight into the invoice and the P&L. Catching it the morning after the trade costs a phone call; catching it at month-end costs a dispute."
    >
      <p className="text-[0.95rem] text-ink-soft italic">The morning exception queue: trades that need a phone call</p>
      <div className="mt-4 border-y border-rule">
        {option && <EChart option={option} height={260} ariaLabel="Confirmation exceptions by type" />}
      </div>
    </Chapter>
  );
}

export function Desk() {
  return (
    <>
      <BookSection />
      <CreditSection />
      <StormSection />
      <MatchingSection />
    </>
  );
}
