import { useEffect, useState } from "react";

import { CHAPTERS } from "../lib/chapters";

/** Plain top bar: name on the left, chapter links on the right. */
export function Header() {
  const [active, setActive] = useState<string>("");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: [0, 0.25, 0.5] },
    );
    CHAPTERS.forEach((c) => {
      const el = document.getElementById(c.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <header className="sticky top-0 z-20 border-b border-rule bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center gap-8 px-4 py-3 sm:px-6">
        <a href="#top" className="shrink-0 font-serif text-xl font-semibold">
          GasBook
        </a>
        <nav className="flex min-w-0 flex-1 gap-5 overflow-x-auto text-[0.95rem]" aria-label="Chapters">
          {CHAPTERS.map((c) => (
            <a
              key={c.id}
              href={`#${c.id}`}
              className="shrink-0 transition-colors hover:text-ink"
              style={{ color: active === c.id ? c.accent : "var(--color-ink-soft)",
                       fontWeight: active === c.id ? 600 : 400 }}
            >
              {c.nav}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
