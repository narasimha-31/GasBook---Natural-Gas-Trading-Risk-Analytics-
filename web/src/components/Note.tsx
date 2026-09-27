import type { ReactNode } from "react";

/**
 * A margin note: sits beside the text on wide screens, drops inline below it on phones.
 * Used for definitions ("Henry Hub is...") instead of hover pop-ups.
 */
export function Note({ term, children }: { term?: string; children: ReactNode }) {
  return (
    <aside className="border-l border-rule pl-4 text-[0.92rem] leading-snug text-ink-soft">
      {term && <div className="mb-0.5 font-semibold text-ink">{term}</div>}
      {children}
    </aside>
  );
}
