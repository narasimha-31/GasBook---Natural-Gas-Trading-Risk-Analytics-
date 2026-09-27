import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([
  LineChart, BarChart, ScatterChart, GridComponent, TooltipComponent, DataZoomComponent, LegendComponent,
  MarkAreaComponent, MarkLineComponent, MarkPointComponent, SVGRenderer,
]);

export type Option = echarts.EChartsCoreOption;

// Shared look: ink on paper, mono labels, one faint horizontal rule set.
export const INK = "#1d2733";
export const INK_SOFT = "#465261";
export const INK_FAINT = "#7d858f";
export const RULE = "#dcd8ce";
export const MONO = "IBM Plex Mono, ui-monospace, monospace";

export const axisBase = {
  axisLine: { lineStyle: { color: INK_SOFT } },
  axisTick: { show: false },
  axisLabel: { color: INK_SOFT, fontFamily: MONO, fontSize: 11 },
  splitLine: { show: false },
};

export const valueAxisBase = {
  ...axisBase,
  axisLine: { show: false },
  splitLine: { show: true, lineStyle: { color: RULE, type: "dashed" as const } },
};

/** Axis title above a vertical value axis (charts using it keep their legend on the right). */
export const yName = (text: string) => ({
  name: text,
  nameLocation: "end" as const,
  nameGap: 12,
  nameTextStyle: { color: INK_SOFT, fontFamily: MONO, fontSize: 10, align: "left" as const },
});

/** Axis title centred under a horizontal value axis. */
export const xName = (text: string) => ({
  name: text,
  nameLocation: "middle" as const,
  nameGap: 28,
  nameTextStyle: { color: INK_SOFT, fontFamily: MONO, fontSize: 10 },
});

export const tooltipBase = {
  trigger: "axis" as const,
  backgroundColor: "#ffffff",
  borderColor: RULE,
  textStyle: { color: INK, fontFamily: MONO, fontSize: 12 },
  axisPointer: { lineStyle: { color: INK_FAINT, type: "dashed" as const } },
};

interface Props {
  option: Option;
  height?: number | string;
  ariaLabel: string;
  /** Merge updates into the chart instead of replacing it (keeps the user's zoom while labels change). */
  merge?: boolean;
  /** Called with the first and last visible category index after the user zooms or drags. */
  onZoom?: (start: number, end: number) => void;
}

/** Thin React wrapper around ECharts (SVG renderer: crisp on paper and print). */
export function EChart({ option, height = 420, ariaLabel, merge = false, onZoom }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const zoomHandler = useRef(onZoom);
  zoomHandler.current = onZoom;

  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.current = c;
    c.on("datazoom", () => {
      const dz = (c.getOption() as { dataZoom?: { startValue?: number; endValue?: number }[] }).dataZoom?.[0];
      if (dz?.startValue != null && dz.endValue != null) zoomHandler.current?.(dz.startValue, dz.endValue);
    });
    const resize = new ResizeObserver(() => c.resize());
    resize.observe(ref.current);
    return () => {
      resize.disconnect();
      c.dispose();
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: !merge, lazyUpdate: true });
  }, [option, merge]);

  return <div ref={ref} style={{ height, width: "100%" }} role="img" aria-label={ariaLabel} />;
}
