import { useEffect, useRef, useState } from "react";

import { CHAPTERS } from "../lib/chapters";

/**
 * Plain top bar: name on the left, chapter links on the right.
 * The current chapter is shown the same way everywhere (dark text + underline), with no colour or
 * weight change, so the bar stays calm and the links never shift as you scroll.
 */
export function Header() {
  const [active, setActive] = useState<string>("");
  const nav = useRef<HTMLElement>(null);

  useEffect(() => {
    // Sub-sections (e.g. desk-credit) count as their parent chapter
    const parentOf = (id: string) => CHAPTERS.find((c) => id === c.id || id.startsWith(`${c.id}-`))?.id ?? "";
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActive(parentOf(visible[0].target.id));
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: [0, 0.25, 0.5] },
    );
    document.querySelectorAll("main section[id]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // On phones the link row scrolls sideways: keep the current chapter in view
  useEffect(() => {
    const link = nav.current?.querySelector<HTMLAnchorElement>(`a[href="#${active}"]`);
    link?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [active]);

  return (
    <header className="sticky top-0 z-20 border-b border-rule bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center gap-8 px-4 sm:px-6">
        <a href="#top" className="shrink-0 py-3 font-serif text-xl font-semibold">
          GasBook
        </a>
        <nav ref={nav} className="flex min-w-0 flex-1 gap-5 overflow-x-auto text-[0.95rem]" aria-label="Chapters">
          {CHAPTERS.map((c) => {
            const on = active === c.id;
            return (
              <a
                key={c.id}
                href={`#${c.id}`}
                aria-current={on ? "true" : undefined}
                className={`shrink-0 border-b-2 py-3 transition-colors ${
                  on ? "border-ink text-ink" : "border-transparent text-ink-soft hover:text-ink"
                }`}
              >
                {c.nav}
              </a>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
