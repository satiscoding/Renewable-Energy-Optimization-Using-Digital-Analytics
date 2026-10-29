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
import { HistoryResponse } from "@/lib/types";
import { formatKw } from "@/lib/utils";

interface OutputHistoryChartProps {
  history: HistoryResponse | null;
  loading: boolean;
}

export const OutputHistoryChart: React.FC<OutputHistoryChartProps> = ({ history, loading }) => {
  if (loading || !history || history.points.length === 0) {
    return (
      <div className="glass-panel p-6 h-80 flex items-center justify-center animate-pulse">
        <span className="text-slate-500 font-mono text-sm">Loading historical telemetry...</span>
      </div>
    );
  }

  const isSolar = history.site_type === "solar";
  const accentColor = isSolar ? "#F59E0B" : "#06B6D4"; // Amber for solar, Cyan for wind
  const gradientId = isSolar ? "solarHistoryGlow" : "windHistoryGlow";

  // Format data for chart
  const chartData = history.points.map((p) => {
    const d = new Date(p.timestamp);
    const timeLabel = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    return {
      time: timeLabel,
      actual: p.actual_kw,
      expected: p.expected_kw ?? (p.actual_kw * 1.02),
      is_anomaly: p.is_anomaly,
    };
  });

  return (
    <div className="glass-panel p-6 flex flex-col h-full">
      <div className="flex items-center justify-between pb-4 border-b border-white/5">
        <div>
          <h3 className="text-base font-semibold text-white">Output History (Trailing 24h)</h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">
            {isSolar ? "15-min intervals • Inverter plant aggregation" : "10-min SCADA intervals • Turbine active power"}
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: accentColor }}></span>
            <span className="text-slate-200 font-medium">Actual kW</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 border-t-2 border-dashed border-slate-300"></span>
            <span className="text-slate-300 font-medium">Expected Benchmark</span>
          </div>
        </div>
      </div>

      <div className="h-72 w-full pt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={accentColor} stopOpacity={0.4} />
                <stop offset="95%" stopColor={accentColor} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
            <XAxis
              dataKey="time"
              stroke="#64748B"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              minTickGap={25}
            />
            <YAxis
              stroke="#64748B"
              fontSize={11}
              domain={[0, (dataMax: number) => Math.ceil(Math.max(dataMax, history.capacity_kw) * 1.05)]}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickFormatter={(v) => `${v}`}
              unit=" kW"
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const d = payload[0].payload;
                const gap = d.expected !== null ? d.expected - d.actual : 0;
                return (
                  <div className="glass-panel p-3 border border-white/15 bg-slate-950/95 text-xs font-mono shadow-2xl z-50">
                    <p className="text-slate-400 font-bold mb-1.5">{d.time}</p>
                    <p className="flex justify-between gap-4" style={{ color: accentColor }}>
                      <span>Actual Output:</span>
                      <span className="font-bold">{formatKw(d.actual)} kW</span>
                    </p>
                    {d.expected !== null && (
                      <p className="flex justify-between gap-4 text-slate-300">
                        <span>Expected Benchmark:</span>
                        <span className="font-bold">{formatKw(d.expected)} kW</span>
                      </p>
                    )}
                    {d.expected !== null && (
                      <p className="flex justify-between gap-4 text-slate-400 pt-1 border-t border-white/5">
                        <span>Delta:</span>
                        <span className={gap > 20 ? "text-red-400 font-bold" : "text-emerald-400 font-bold"}>
                          {gap > 0 ? `-${formatKw(gap)}` : `+${formatKw(Math.abs(gap))}`} kW
                        </span>
                      </p>
                    )}
                    {d.is_anomaly === 1 && (
                      <p className="text-red-400 font-semibold mt-1">⚠️ Flagged Anomaly</p>
                    )}
                  </div>
                );
              }}
            />
            {/* Actual Output Area */}
            <Area
              type="monotone"
              dataKey="actual"
              stroke={accentColor}
              strokeWidth={2.2}
              fillOpacity={1}
              fill={`url(#${gradientId})`}
              name="Actual Power"
            />
            {/* Highly visible Expected Benchmark Dashed Line */}
            <Line
              type="monotone"
              dataKey="expected"
              stroke="#CBD5E1"
              strokeWidth={2.4}
              strokeDasharray="6 4"
              dot={false}
              connectNulls={true}
              name="Expected Benchmark"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
