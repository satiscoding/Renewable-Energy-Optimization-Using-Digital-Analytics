"use client";

import React, { useState } from "react";
import { Activity, Zap, RefreshCw, AlertTriangle } from "lucide-react";
import { triggerSimulatorTick, setSiteAnomaly } from "@/lib/api";

interface HeaderProps {
  currentSiteId: string;
  onRefresh: () => void;
}

export const Header: React.FC<HeaderProps> = ({ currentSiteId, onRefresh }) => {
  const [isTickLoading, setIsTickLoading] = useState(false);
  const [activeAnomaly, setActiveAnomaly] = useState<string>("normal");

  const handleManualTick = async () => {
    try {
      setIsTickLoading(true);
      await triggerSimulatorTick();
      onRefresh();
    } finally {
      setIsTickLoading(false);
    }
  };

  const handleAnomalyChange = async (mode: string) => {
    setActiveAnomaly(mode);
    await setSiteAnomaly(currentSiteId, mode);
    onRefresh();
  };

  return (
    <header className="border-b border-white/10 bg-slate-950/70 backdrop-blur-md sticky top-0 z-50 px-4 lg:px-8 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        
        {/* Title and Live Status */}
        <div className="flex items-center space-x-3.5">
          <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Zap className="w-6 h-6 animate-pulse-slow" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Solar & Wind Control Room
              </h1>
              <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                LIVE FEED (5s)
              </div>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Phase-II Digital Analytics & Optimization Platform
            </p>
          </div>
        </div>

        {/* Viva / Interactive Demo Controls */}
        <div className="flex items-center flex-wrap gap-2.5 w-full md:w-auto">
          {/* Anomaly Injector Selector for Viva Demonstration */}
          <div className="flex items-center bg-slate-900/90 border border-white/10 rounded-lg p-1 text-xs">
            <span className="text-slate-400 px-2 flex items-center gap-1 font-mono">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              Demo Inject:
            </span>
            <button
              onClick={() => handleAnomalyChange("normal")}
              className={`px-2 py-1 rounded transition-colors ${activeAnomaly === "normal" ? "bg-emerald-500/20 text-emerald-300 font-semibold" : "text-slate-400 hover:text-white"}`}
            >
              Nominal
            </button>
            <button
              onClick={() => handleAnomalyChange(currentSiteId === "solar-plant-1" ? "soiling" : "wind_shortfall")}
              className={`px-2 py-1 rounded transition-colors ${activeAnomaly === "soiling" || activeAnomaly === "wind_shortfall" ? "bg-amber-500/20 text-amber-300 font-semibold" : "text-slate-400 hover:text-white"}`}
            >
              {currentSiteId === "solar-plant-1" ? "Soiling" : "Shortfall"}
            </button>
            <button
              onClick={() => handleAnomalyChange("sudden_drop")}
              className={`px-2 py-1 rounded transition-colors ${activeAnomaly === "sudden_drop" ? "bg-red-500/20 text-red-300 font-semibold" : "text-slate-400 hover:text-white"}`}
            >
              Sudden Drop
            </button>
          </div>

          {/* Manual Tick / Refresh Button */}
          <button
            onClick={handleManualTick}
            disabled={isTickLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-slate-300 hover:text-white transition-all shadow-sm active:scale-95 disabled:opacity-50"
            title="Step simulator by 1 interval"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTickLoading ? "animate-spin text-amber-400" : ""}`} />
            Tick Step
          </button>
        </div>

      </div>
    </header>
  );
};
