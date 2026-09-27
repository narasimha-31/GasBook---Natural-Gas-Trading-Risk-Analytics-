import { useEffect, useState } from "react";

// Every exported file starts with this block (see src/gasbook/export_dashboard.py).
export interface Meta {
  title: string;
  source: string;
  period: string;
  simulated: boolean;
  notes: string;
}

export interface DataFile<H = Record<string, unknown>> {
  meta: Meta;
  headline: H;
  [key: string]: unknown;
}

const cache = new Map<string, Promise<unknown>>();

function load<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    const url = `${import.meta.env.BASE_URL}data/${name}.json`;
    cache.set(
      name,
      fetch(url).then((r) => {
        if (!r.ok) throw new Error(`${url}: ${r.status}`);
        return r.json();
      }),
    );
  }
  return cache.get(name) as Promise<T>;
}

/** Load one exported JSON file. Returns undefined while loading. */
export function useData<T>(name: string): T | undefined {
  const [data, setData] = useState<T>();
  useEffect(() => {
    let alive = true;
    load<T>(name)
      .then((d) => alive && setData(d))
      .catch((e) => console.error(e));
    return () => {
      alive = false;
    };
  }, [name]);
  return data;
}
