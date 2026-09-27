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
  /** Margin notes (definitions) shown beside the answer. */
  notes?: ReactNode;
  children?: ReactNode;
  /** One line on why a desk should care. */
  why?: ReactNode;
  /** Optional extra detail behind a toggle. */
  details?: ReactNode;
}

/** A chapter: a question, a plain answer, one main visual, and why it matters. */
export function Chapter({ id, number, accent, question, meta, answer, notes, children, why, details }: Props) {
  const reduce = useReducedMotion();
  const [open, setOpen] = useState(false);

  return (
    <motion.section
      id={id}
      className="border-t border-rule py-16 sm:py-20"
      initial={reduce ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: "easeOut" }}
    >
      <div className="grid gap-10 md:grid-cols-12 md:gap-12">
        <div className="md:col-span-8">
          <div className="flex items-center justify-between gap-4">
            <p className="text-[0.95rem] italic" style={{ color: accent }}>
              Chapter {number}
            </p>
            {meta && <Badge simulated={meta.simulated} />}
          </div>
          <h2 className="mt-3 font-serif text-3xl leading-tight font-semibold sm:text-4xl">{question}</h2>
          <div className="mt-5 text-xl leading-relaxed text-ink-soft">{answer}</div>
        </div>
        {notes && <div className="space-y-6 md:col-span-4 md:pt-10">{notes}</div>}
      </div>

      {children && <div className="mt-10">{children}</div>}

      {why && (
        <p className="mt-10 max-w-3xl border-l-2 pl-4 text-lg leading-relaxed" style={{ borderColor: accent }}>
          <span className="font-semibold">Why it matters. </span>
          {why}
        </p>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-[0.9rem] text-ink-faint">
        {meta && (
          <span>
            Source: {meta.source}. {meta.period}.
          </span>
        )}
        {details && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="underline decoration-rule underline-offset-4 hover:text-ink"
            aria-expanded={open}
          >
            {open ? "Hide the details" : "Show the details"}
          </button>
        )}
      </div>
      {details && open && <div className="mt-6">{details}</div>}
    </motion.section>
  );
}
