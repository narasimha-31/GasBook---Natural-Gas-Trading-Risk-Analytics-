import { motion, useReducedMotion } from "motion/react";
import { useState, type ReactNode } from "react";

import type { Meta } from "../lib/data";
import { Badge } from "./Badge";

interface Props {
  id: string;
  number: number;
  accent: string;
  question: string;
  meta?: Meta;
  /** One-sentence answer, shown large. */
  answer: ReactNode;
  children?: ReactNode;
  /** One line on why a desk should care. */
  why?: ReactNode;
  /** Optional extra detail behind a toggle. */
  details?: ReactNode;
}

/** A chapter = a question, a one-sentence answer, one main visual, and why it matters. */
export function Chapter({ id, number, accent, question, meta, answer, children, why, details }: Props) {
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);

  return (
    <motion.section
      id={id}
      className="border-t border-rule py-14 sm:py-20"
      initial={reduce ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: "easeOut" }}
    >
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <span className="h-5 w-1 rounded-full" style={{ background: accent }} aria-hidden />
        <span className="num text-sm font-semibold tracking-wide" style={{ color: accent }}>
          {String(number).padStart(2, "0")}
        </span>
        {meta && <Badge simulated={meta.simulated} />}
      </div>

      <h2 className="max-w-3xl font-serif text-3xl leading-tight font-semibold sm:text-4xl">{question}</h2>
      <p className="mt-5 max-w-3xl font-serif text-xl leading-relaxed text-ink-soft sm:text-2xl">{answer}</p>

      {children && <div className="mt-10">{children}</div>}

      {why && (
        <p className="mt-8 max-w-3xl border-l-2 pl-4 text-base leading-relaxed" style={{ borderColor: accent }}>
          <span className="font-semibold">Why it matters: </span>
          {why}
        </p>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-ink-faint">
        {meta && (
          <span>
            Source: {meta.source} · {meta.period}
          </span>
        )}
        {details && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="font-medium underline decoration-rule underline-offset-4 hover:text-ink"
            aria-expanded={open}
          >
            {open ? "Hide the details" : "See the details"}
          </button>
        )}
      </div>
      {details && open && <div className="mt-6">{details}</div>}
    </motion.section>
  );
}
