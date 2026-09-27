/** Small, plain controls: a two-way toggle and a from/to year picker. */

interface ToggleProps<T extends string> {
  label: string;
  options: { value: T; text: string }[];
  value: T;
  onChange: (v: T) => void;
  accent: string;
}

export function Toggle<T extends string>({ label, options, value, onChange, accent }: ToggleProps<T>) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[0.95rem]" role="radiogroup" aria-label={label}>
      <span className="text-ink-faint">{label}</span>
      <div className="flex overflow-hidden rounded border border-ink/25">
        {options.map((o) => {
          const on = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(o.value)}
              className="px-3 py-1 transition-colors"
              style={on ? { background: accent, color: "#f8f4ea" } : { color: "var(--color-ink-soft)" }}
            >
              {o.text}
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface YearsProps {
  min: number;
  max: number;
  from: number;
  to: number;
  onChange: (from: number, to: number) => void;
}

export function YearRange({ min, max, from, to, onChange }: YearsProps) {
  const years = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  const select = "rounded border border-ink/25 bg-transparent px-2 py-1 num text-[0.9rem]";
  return (
    <div className="flex flex-wrap items-center gap-2 text-[0.95rem]">
      <span className="text-ink-faint">Years</span>
      <select className={select} value={from} aria-label="From year"
        onChange={(e) => onChange(Math.min(+e.target.value, to), to)}>
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
      <span className="text-ink-faint">to</span>
      <select className={select} value={to} aria-label="To year"
        onChange={(e) => onChange(from, Math.max(+e.target.value, from))}>
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
      {(from !== min || to !== max) && (
        <button type="button" className="text-ink-faint underline underline-offset-4 hover:text-ink"
          onClick={() => onChange(min, max)}>
          All years
        </button>
      )}
    </div>
  );
}
