import { animate, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

interface Props {
  value: number;
  format: (v: number) => string;
  duration?: number;
}

/** A number that counts up once when it scrolls into view. */
export function CountUp({ value, format, duration = 1.2 }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? value : 0);

  useEffect(() => {
    if (!inView || reduce) {
      if (reduce) setShown(value);
      return;
    }
    const controls = animate(0, value, { duration, ease: [0.16, 1, 0.3, 1], onUpdate: setShown });
    return () => controls.stop();
  }, [inView, reduce, value, duration]);

  return (
    <span ref={ref} className="num">
      {format(shown)}
    </span>
  );
}
