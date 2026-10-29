"use client";

import React from "react";
import { CheckCircle2, AlertOctagon, TrendingUp, TrendingDown, Gauge, Cpu } from "lucide-react";
import { SiteStatus } from "@/lib/types";
import { formatKw, formatKwh } from "@/lib/utils";

interface PrimaryStatusCardProps {
  status: SiteStatus | null;
  loading: boolean;
}

export const PrimaryStatusCard: React.FC<PrimaryStatusCardProps> = ({ status, loading }) => {
  if (loading || !status) {
    return (
      <div className="glass-panel-primary p-6 animate-pulse">
        <div className="h-6 w-48 bg-white/10 rounded mb-4"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="h-16 bg-white/5 rounded"></div>
          <div className="h-16 bg-white/5 rounded"></div>
          <div className="h-16 bg-white/5 rounded"></div>
          <div className="h-16 bg-white/5 rounded"></div>
        </div>
      </div>
    );
  }

  const isHealthy = status.health === "healthy";
  const isSolar = status.site_type === "solar";
  const gapPct = status.gap_pct;

  return (
    <div
      className={`glass-panel-primary p-6 md:p-8 relative overflow-hidden transition-all duration-300 ${
        isHealthy
          ? isSolar
            ? "border-amber-500/20 shadow-glass-amber"
            : "border-cyan-500/20 shadow-glass-cyan"
          : "border-red-500/30 shadow-[0_0_35px_-5px_rgba(239,68,68,0.25)]"
      }`}
    >
      {/* Ambient background glow accent */}
      <div
        className={`absolute -top-24 -right-24 w-72 h-72 rounded-full blur-3xl opacity-20 pointer-events-none ${
          isHealthy ? (isSolar ? "bg-amber-500" : "bg-cyan-500") : "bg-red-500"
        }`}
      />

      {/* Header bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-6 border-b border-white/10">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-white tracking-tight">{status.site_name}</h2>
            <span className="text-xs uppercase tracking-wider px-2.5 py-0.5 rounded bg-white/10 border border-white/15 text-slate-300 font-mono">
              {isSolar ? "Plant-Level Total" : "Single Turbine SCADA"}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Rated Capacity: {formatKw(status.capacity_kw)} kW • Last Interval: {new Date(status.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </p>
        </div>

        {/* Dynamic Health Badge */}
        <div
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full border text-xs font-semibold uppercase tracking-wider transition-all ${
            isHealthy
              ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400 shadow-glass-emerald"
              : "bg-red-500/20 border-red-500/50 text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.35)] animate-pulse"
          }`}
        >
          {isHealthy ? (
            <>
              <CheckCircle2 className="w-4 h-4" />
              <span>Healthy</span>
            </>
          ) : (
            <>
              <AlertOctagon className="w-4 h-4" />
              <span>Anomaly Detected ({status.active_issues_count} Active)</span>
            </>
          )}
        </div>
      </div>

      {/* Main Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 pt-6">
        
        {/* Actual Power Output */}
        <div className="flex flex-col space-y-1">
          <span className="text-xs uppercase font-medium tracking-wider text-slate-400">
            Actual Power Output
          </span>
          <div className="flex items-baseline gap-2">
            <span className={`text-4xl lg:text-5xl font-extrabold font-mono tracking-tight tabular-nums ${
              isSolar ? "text-amber-400" : "text-cyan-400"
            }`}>
              {formatKw(status.actual_kw)}
            </span>
            <span className="text-sm font-semibold text-slate-400 font-mono">kW</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-mono">
            <Cpu className="w-3.5 h-3.5 text-slate-400" />
            <span>Current Load: <strong className={isSolar ? "text-amber-300" : "text-cyan-300"}>{status.current_load_pct?.toFixed(1) ?? (status.actual_kw / status.capacity_kw * 100).toFixed(1)}%</strong> of rated</span>
          </div>
        </div>

        {/* Expected Power Output */}
        <div className="flex flex-col space-y-1">
          <span className="text-xs uppercase font-medium tracking-wider text-slate-400">
            Expected Benchmark
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl lg:text-4xl font-bold font-mono text-slate-300 tabular-nums">
              {formatKw(status.expected_kw)}
            </span>
            <span className="text-sm font-semibold text-slate-400 font-mono">kW</span>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            {isSolar ? "Irradiance & Temp Model" : "Theoretical Power Curve"}
          </span>
        </div>

        {/* Generation Discrepancy Gap */}
        <div className="flex flex-col space-y-1">
          <span className="text-xs uppercase font-medium tracking-wider text-slate-400">
            Generation Delta
          </span>
          <div className="flex items-baseline gap-2">
            <span
              className={`text-3xl lg:text-4xl font-bold font-mono tabular-nums flex items-center gap-1 ${
                Math.abs(gapPct) <= 8
                  ? "text-emerald-400"
                  : gapPct > 8
                  ? "text-red-400"
                  : "text-blue-400"
              }`}
            >
              {gapPct > 0 ? (
                <TrendingDown className="w-5 h-5 inline text-red-400" />
              ) : (
                <TrendingUp className="w-5 h-5 inline text-emerald-400" />
              )}
              {gapPct > 0 ? `-${gapPct.toFixed(1)}` : `+${Math.abs(gapPct).toFixed(1)}`}%
            </span>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Delta: {formatKw(Math.abs(status.gap_kw))} kW
          </span>
        </div>

        {/* Daily Cumulative Yield (kWh) & True Daily Capacity Factor */}
        <div className="flex flex-col space-y-1">
          <span className="text-xs uppercase font-medium tracking-wider text-slate-400">
            Daily Yield
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl lg:text-4xl font-extrabold font-mono text-emerald-400 tabular-nums">
              {formatKwh(status.daily_yield_kwh)}
            </span>
            <span className="text-sm font-semibold text-slate-400 font-mono">kWh</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-mono">
            <Gauge className="w-3.5 h-3.5 text-emerald-400" />
            <span>Daily Capacity Factor: <strong className="text-emerald-300">{status.daily_capacity_factor_pct?.toFixed(1) ?? status.capacity_factor_pct.toFixed(1)}%</strong></span>
          </div>
        </div>

      </div>
    </div>
  );
};
