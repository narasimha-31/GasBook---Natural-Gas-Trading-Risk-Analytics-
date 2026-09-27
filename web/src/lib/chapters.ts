// The story, in order. Accent = the chapter's color token in styles.css.
export interface ChapterInfo {
  id: string;
  nav: string;
  accent: string;
}

export const CHAPTERS: ChapterInfo[] = [
  { id: "prices", nav: "Prices", accent: "var(--color-market)" },
  { id: "risk", nav: "Risk", accent: "var(--color-risk)" },
  { id: "hedges", nav: "Hedges", accent: "var(--color-hedge)" },
  { id: "signals", nav: "Signals", accent: "var(--color-signals)" },
  { id: "forecast", nav: "Forecast", accent: "var(--color-forecast)" },
  { id: "weather", nav: "Weather", accent: "var(--color-weather)" },
  { id: "desk", nav: "The desk", accent: "var(--color-desk)" },
  { id: "context", nav: "Context", accent: "var(--color-context)" },
  { id: "method", nav: "Method", accent: "var(--color-ink-soft)" },
];

export const accentOf = (id: string) => CHAPTERS.find((c) => c.id === id)?.accent ?? "var(--color-ink)";
