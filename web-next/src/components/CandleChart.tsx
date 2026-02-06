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
  theme = "dark",
}: {
  candles: Candle[];
  forecast: ForecastPoint[];
  entry?: number;
  stop?: number;
  takeProfit?: number;
  theme?: "dark" | "eink";
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!ref.current) return;

    const isEink = theme === "eink";

    const chart: any = createChart(ref.current, {
      layout: {
        background: { type: ColorType.Solid, color: isEink ? "#ffffff" : "#0a0a0a" },
        textColor: isEink ? "#111111" : "#d4d4d8",
      },
      grid: {
        vertLines: { color: isEink ? "#dddddd" : "#222" },
        horzLines: { color: isEink ? "#dddddd" : "#222" },
      },
      timeScale: { borderColor: isEink ? "#bbbbbb" : "#333" },
      rightPriceScale: { borderColor: isEink ? "#bbbbbb" : "#333" },
      height: 320,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: isEink ? "#111111" : "#22c55e",
      downColor: isEink ? "#777777" : "#ef4444",
      borderDownColor: isEink ? "#777777" : "#ef4444",
      borderUpColor: isEink ? "#111111" : "#22c55e",
      wickDownColor: isEink ? "#777777" : "#ef4444",
      wickUpColor: isEink ? "#111111" : "#22c55e",
    });

    const lineSeries = chart.addSeries(LineSeries, {
      color: isEink ? "#111111" : "#60a5fa",
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

    if (typeof entry === "number" && Number.isFinite(entry)) makeLine(entry, "Entry", isEink ? "#111111" : "#38bdf8");
    if (typeof stop === "number" && Number.isFinite(stop)) makeLine(stop, "Stop", isEink ? "#777777" : "#f87171");
    if (typeof takeProfit === "number" && Number.isFinite(takeProfit)) makeLine(takeProfit, "TP", isEink ? "#111111" : "#34d399");

    chart.timeScale().fitContent();

    chartRef.current = chart;
    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, forecast, theme]);

  return <div ref={ref} className="w-full" />;
}
