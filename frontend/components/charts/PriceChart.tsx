"use client";
import * as React from "react";
import {
  createChart,
  ColorType,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  HistogramData,
  LineData,
  Time,
} from "lightweight-charts";
import type { OhlcRow } from "@/lib/types";

export type Overlay = {
  label: string;
  color: string;
  values: { time: number; value: number }[];
};

type Props = {
  data: OhlcRow[];
  height?: number;
  overlays?: Overlay[];
  markerLevels?: { label: string; price: number; color: string }[];
};

export function PriceChart({ data, height = 420, overlays = [], markerLevels = [] }: Props) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const chartRef = React.useRef<IChartApi | null>(null);
  const candleRef = React.useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = React.useRef<ISeriesApi<"Histogram"> | null>(null);

  React.useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        horzLines: { color: "rgba(255,255,255,0.05)" },
        vertLines: { color: "rgba(255,255,255,0.05)" },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 },
      autoSize: true,
      height,
    });

    const candle = chart.addCandlestickSeries({
      upColor: "#22c55e",
      borderUpColor: "#22c55e",
      wickUpColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      wickDownColor: "#ef4444",
    });

    const volume = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: "#374151",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

    chartRef.current = chart;
    candleRef.current = candle;
    volRef.current = volume;

    const onResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volRef.current = null;
    };
  }, [height]);

  React.useEffect(() => {
    if (!chartRef.current || !candleRef.current || !volRef.current) return;
    if (!data || data.length === 0) return;

    const candleData: CandlestickData[] = data.map((d) => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    const volData: HistogramData[] = data.map((d) => ({
      time: d.time as Time,
      value: d.volume,
      color: d.close >= d.open ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.4)",
    }));

    candleRef.current.setData(candleData);
    volRef.current.setData(volData);

    // Clear and add overlays as new line series each render
    overlays.forEach((ov) => {
      const series = chartRef.current!.addLineSeries({
        color: ov.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      const pts: LineData[] = ov.values
        .filter((v) => Number.isFinite(v.value))
        .map((v) => ({ time: v.time as Time, value: v.value }));
      series.setData(pts);
    });

    // Price levels (SL / Targets)
    if (candleRef.current && markerLevels.length) {
      markerLevels.forEach((m) => {
        candleRef.current!.createPriceLine({
          price: m.price,
          color: m.color,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: m.label,
        });
      });
    }

    chartRef.current.timeScale().fitContent();
  }, [data, overlays, markerLevels]);

  return <div ref={containerRef} className="w-full" style={{ height }} />;
}
