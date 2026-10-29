"use client";

import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from "recharts";
import { ForecastResponse } from "@/lib/types";
import { formatKw } from "@/lib/utils";
import { BrainCircuit } from "lucide-react";

interface ForecastChartProps {
  forecast: ForecastResponse | null;
  loading: boolean;
}

export const ForecastChart: React.FC<ForecastChartProps> = ({ forecast, loading }) => {
  if (loading || !forecast || forecast.points.length === 0) {
    return (
      <div className="glass-panel p-6 h-80 flex items-center justify-center animate-pulse">
        <span className="text-slate-500 font-mono text-sm">Generating synchronized forecast...</span>
      </div>
    );
  }

  const modelMetrics = forecast.evaluation_metrics[forecast.model_used] || Object.values(forecast.evaluation_metrics)[0] || {};
  const horizons = modelMetrics.horizons || null;
  const mae = modelMetrics.mae ?? "--";
  const rmse = modelMetrics.rmse ?? "--";

  const chartData = forecast.points.map((p) => {
    const d = new Date(p.timestamp);
    const timeLabel = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    return {
      time: timeLabel,
      predicted: p.predicted_kw,
      low: p.confidence_low_kw ?? p.predicted_kw * 0.9,
      high: p.confidence_high_kw ?? p.predicted_kw * 1.1,
    };
  });

  return (
    <div className="glass-panel p-6 flex flex-col h-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-white/5 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-white">Generation Forecast (Next 2-6h)</h3>
            <span className="px-2 py-0.5 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300 text-xs font-mono flex items-center gap-1">
              <BrainCircuit className="w-3 h-3 text-purple-400" />
              {forecast.model_used}
            </span>
          </div>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            Synchronized to latest interval • Open-Meteo weather features & continuity smoothing
          </p>
        </div>

        {/* Multi-horizon held-out metrics */}
        <div className="flex items-center flex-wrap gap-2 text-xs font-mono text-slate-400 bg-white/5 px-2.5 py-1 rounded-lg border border-white/5 w-fit">
          {horizons ? (
            <>
              <span>+1h MAE: <strong className="text-purple-300">{horizons["+1h"]?.mae ?? mae} kW</strong></span>
              <span>•</span>
              <span>+3h: <strong className="text-purple-300">{horizons["+3h"]?.mae ?? mae} kW</strong></span>
              <span>•</span>
              <span>+6h: <strong className="text-purple-300">{horizons["+6h"]?.mae ?? mae} kW</strong></span>
            </>
          ) : (
            <>
              <span>MAE: <strong className="text-purple-300">{mae} kW</strong></span>
              <span>•</span>
              <span>RMSE: <strong className="text-purple-300">{rmse} kW</strong></span>
            </>
          )}
        </div>
      </div>

      <div className="h-72 w-full pt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="forecastUncertainty" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#A855F7" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#A855F7" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="#64748B"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              minTickGap={20}
            />
            <YAxis
              stroke="#64748B"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickFormatter={(v) => `${v}`}
              unit=" kW"
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="glass-panel p-3 border border-purple-500/20 bg-slate-950/95 text-xs font-mono shadow-2xl z-50">
                    <p className="text-slate-400 font-bold mb-1.5">{d.time} (Forecast)</p>
                    <p className="flex justify-between gap-4 text-purple-300">
                      <span>Predicted:</span>
                      <span className="font-bold">{formatKw(d.predicted)} kW</span>
                    </p>
                    <p className="flex justify-between gap-4 text-slate-400">
                      <span>Confidence Range:</span>
                      <span>{formatKw(d.low)} – {formatKw(d.high)} kW</span>
                    </p>
                  </div>
                );
              }}
            />
            {/* Shaded uncertainty envelope */}
            <Area
              type="monotone"
              dataKey="high"
              stroke="transparent"
              fillOpacity={1}
              fill="url(#forecastUncertainty)"
            />
            {/* Main forecast dashed line */}
            <Line
              type="monotone"
              dataKey="predicted"
              stroke="#A855F7"
              strokeWidth={2.4}
              strokeDasharray="5 5"
              dot={{ r: 2.5, fill: "#C084FC" }}
              activeDot={{ r: 5, fill: "#E9D5FF" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
