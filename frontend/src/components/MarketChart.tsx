
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  type CandlestickData,
  type IChartApi,
  type Time,
} from "lightweight-charts";

type HistoryItem = {
  captured_at: string;
  currency: string;
  current_price: number;
  total_volume: number;
};

type HistoryResponse = {
  coin: {
    coin_id: string;
    symbol: string;
    name: string;
  };
  count: number;
  history: HistoryItem[];
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

const ASSETS = [
  { id: "bitcoin", symbol: "BTC", name: "Bitcoin" },
  { id: "ethereum", symbol: "ETH", name: "Ethereum" },
  { id: "tether", symbol: "USDT", name: "Tether" },
  { id: "binancecoin", symbol: "BNB", name: "BNB" },
  { id: "ripple", symbol: "XRP", name: "XRP" },
];

const PERIODS = [
  { label: "15M", seconds: 15 * 60 },
  { label: "1H", seconds: 60 * 60 },
  { label: "4H", seconds: 4 * 60 * 60 },
  { label: "1D", seconds: 24 * 60 * 60 },
];

export default function MarketChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const [asset, setAsset] = useState("bitcoin");
  const [period, setPeriod] = useState("15M");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [currency, setCurrency] = useState("usd");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const selectedAsset = ASSETS.find((item) => item.id === asset);
  const selectedPeriod = PERIODS.find((item) => item.label === period)!;

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      setLoading(true);
      setError("");

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/market/history/${asset}`,
          { cache: "no-store" }
        );

        if (!response.ok) {
          throw new Error(`行情接口返回 HTTP ${response.status}`);
        }

        const payload: HistoryResponse = await response.json();

        if (!Array.isArray(payload.history)) {
          throw new Error("历史行情数据格式不正确");
        }

        if (!cancelled) {
          setHistory(payload.history);
          setCurrency(
            payload.history[0]?.currency?.toLowerCase() || "usd"
          );
        }
      } catch (err) {
        if (!cancelled) {
          setHistory([]);
          setError(
            err instanceof Error ? err.message : "历史行情加载失败"
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [asset]);

  const candles = useMemo<CandlestickData<Time>[]>(() => {
    const sorted = [...history]
      .filter(
        (item) =>
          Number.isFinite(item.current_price) &&
          item.current_price > 0 &&
          Number.isFinite(new Date(item.captured_at).getTime())
      )
      .sort(
        (a, b) =>
          new Date(a.captured_at).getTime() -
          new Date(b.captured_at).getTime()
      );

    const buckets = new Map<
      number,
      { open: number; high: number; low: number; close: number }
    >();

    for (const item of sorted) {
      const timestamp = Math.floor(
        new Date(item.captured_at).getTime() / 1000
      );
      const bucketTime =
        Math.floor(timestamp / selectedPeriod.seconds) *
        selectedPeriod.seconds;

      const price = item.current_price;
      const existing = buckets.get(bucketTime);

      if (!existing) {
        buckets.set(bucketTime, {
          open: price,
          high: price,
          low: price,
          close: price,
        });
      } else {
        existing.high = Math.max(existing.high, price);
        existing.low = Math.min(existing.low, price);
        existing.close = price;
      }
    }

    return Array.from(buckets.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([time, candle]) => ({
        time: time as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }));
  }, [history, selectedPeriod]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 340,
      layout: {
        background: { type: ColorType.Solid, color: "#0b1220" },
        textColor: "#8b9bb4",
        fontFamily: "Arial, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      rightPriceScale: {
        borderColor: "rgba(148,163,184,0.15)",
      },
      timeScale: {
        borderColor: "rgba(148,163,184,0.15)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: "rgba(56,189,248,0.45)" },
        horzLine: { color: "rgba(56,189,248,0.45)" },
      },
    });

    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00c087",
      downColor: "#f23645",
      borderUpColor: "#00c087",
      borderDownColor: "#f23645",
      wickUpColor: "#00c087",
      wickDownColor: "#f23645",
    });

    candleSeries.setData(candles);
    chart.timeScale().fitContent();

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width && chartRef.current === chart) {
        chart.applyOptions({ width });
      }
    });

    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [candles]);

  const coverageText =
    history.length > 0
      ? `${history.length} 条历史快照 · ${candles.length} 根聚合蜡烛`
      : "暂无历史数据";

  return (
    <div className="w-full space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {ASSETS.map((item) => (
            <button
              key={item.id}
              onClick={() => setAsset(item.id)}
              className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${
                asset === item.id
                  ? "bg-cyan-400/15 text-cyan-300 ring-1 ring-cyan-400/40"
                  : "bg-white/5 text-slate-400 hover:bg-white/10"
              }`}
            >
              {item.symbol}
            </button>
          ))}
        </div>

        <div className="flex gap-1 rounded-lg bg-white/5 p-1">
          {PERIODS.map((item) => (
            <button
              key={item.label}
              onClick={() => setPeriod(item.label)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                period === item.label
                  ? "bg-cyan-400/20 text-cyan-300"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-white">
            {selectedAsset?.name || asset} / {currency.toUpperCase()}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {coverageText}
          </div>
        </div>

        <div className="text-xs text-slate-500">
          {loading ? "正在同步历史行情..." : "SQLite 历史快照"}
        </div>
      </div>

      <div className="relative min-h-[340px] w-full overflow-hidden rounded-xl border border-white/5 bg-[#0b1220]">
        <div ref={containerRef} className="w-full" />

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0b1220]/70 text-sm text-slate-400">
            正在加载真实行情...
          </div>
        )}

        {!loading && error && (
          <div className="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-rose-400">
            {error}
          </div>
        )}

        {!loading && !error && candles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">
            暂无可绘制的历史快照
          </div>
        )}
      </div>

      <div className="text-xs leading-relaxed text-slate-500">
        数据说明：蜡烛图由 CoinGecko 每次采集的历史价格快照聚合生成，
        并非交易所原生 OHLC K 线。当前 high / low 仅代表采样期间观察到的价格极值。
        不同周期的数据覆盖范围取决于数据库已积累的历史记录。
      </div>
    </div>
  );
}
