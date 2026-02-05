"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
} from "lightweight-charts";

type Candle = { date: string; open: number; high: number; low: number; close: number };

type ForecastPoint = { date: string; close: number };

export default function CandleChart({
  candles,
  forecast,
  entry,
  stop,
  takeProfit,
}: {
  candles: Candle[];
  forecast: ForecastPoint[];
  entry?: number;
  stop?: number;
  takeProfit?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!ref.current) return;

    const chart: any = createChart(ref.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#d4d4d8",
      },
      grid: {
        vertLines: { color: "#222" },
        horzLines: { color: "#222" },
      },
      timeScale: { borderColor: "#333" },
      rightPriceScale: { borderColor: "#333" },
      height: 320,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    const lineSeries = chart.addSeries(LineSeries, {
      color: "#60a5fa",
      lineWidth: 2,
    });

    candleSeries.setData(
      candles.map((c) => ({
        time: c.date,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // Forecast: draw as line
    const fc = forecast.map((p) => ({ time: p.date, value: p.close }));
    lineSeries.setData(fc);

    // Horizontal price markers
    const makeLine = (price: number, title: string, color: string) => {
      try {
        candleSeries.createPriceLine({
          price,
          title,
          color,
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
        });
      } catch {
        // best-effort
      }
    };

    if (typeof entry === "number" && Number.isFinite(entry)) makeLine(entry, "Entry", "#38bdf8");
    if (typeof stop === "number" && Number.isFinite(stop)) makeLine(stop, "Stop", "#f87171");
    if (typeof takeProfit === "number" && Number.isFinite(takeProfit)) makeLine(takeProfit, "TP", "#34d399");

    chart.timeScale().fitContent();

    chartRef.current = chart;
    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, forecast]);

  return <div ref={ref} className="w-full" />;
}
