"use client";

import React from "react";
import { AlertCircle, AlertTriangle, Info, CheckCircle2, ShieldCheck } from "lucide-react";
import { RecommendationItem } from "@/lib/types";

interface RecommendationsPanelProps {
  recommendations: RecommendationItem[];
  loading: boolean;
}

export const RecommendationsPanel: React.FC<RecommendationsPanelProps> = ({ recommendations, loading }) => {
  if (loading) {
    return (
      <div className="glass-panel p-6 animate-pulse">
        <div className="h-6 w-48 bg-white/10 rounded mb-4"></div>
        <div className="space-y-3">
          <div className="h-20 bg-white/5 rounded"></div>
          <div className="h-20 bg-white/5 rounded"></div>
        </div>
      </div>
    );
  }

  const activeRecs = recommendations.filter((r) => r.status === "active");

  return (
    <div className="glass-panel p-6 flex flex-col h-full">
      <div className="flex items-center justify-between pb-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-white">AI Diagnostic & Operational Recommendations</h3>
          <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 font-mono text-slate-300">
            {activeRecs.length} Active
          </span>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-slate-400 font-mono">
          <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
          <span>Advisory Only (No SCADA Actuation)</span>
        </div>
      </div>

      <div className="pt-4 flex-1 overflow-y-auto space-y-3 pr-1 max-h-[360px]">
        {activeRecs.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center bg-white/[0.02] border border-white/5 rounded-lg">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mb-2" />
            <h4 className="text-sm font-semibold text-slate-200">All Generation Parameters Nominal</h4>
            <p className="text-xs text-slate-400 mt-1 max-w-sm">
              Actual power tracks benchmark within acceptable statistical tolerances. No soiling, shading, or mechanical shortfall detected.
            </p>
          </div>
        ) : (
          activeRecs.map((rec) => {
            const isCritical = rec.severity === "critical";
            const isWarning = rec.severity === "warning";

            return (
              <div
                key={rec.id}
                className={`p-4 rounded-lg border transition-all ${
                  isCritical
                    ? "bg-red-500/10 border-red-500/30 text-red-200 shadow-[0_0_15px_-3px_rgba(239,68,68,0.2)]"
                    : isWarning
                    ? "bg-amber-500/10 border-amber-500/30 text-amber-200 shadow-[0_0_15px_-3px_rgba(245,158,11,0.15)]"
                    : "bg-blue-500/10 border-blue-500/30 text-blue-200"
                }`}
              >
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <div className="flex items-center gap-2">
                    {isCritical ? (
                      <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                    ) : isWarning ? (
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    ) : (
                      <Info className="w-4 h-4 text-blue-400 shrink-0" />
                    )}
                    <span className="text-xs font-bold uppercase tracking-wider font-mono">
                      [{rec.severity}] {rec.issue_type.replace("_", " ")}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400 shrink-0">
                    {rec.relative_time}
                  </span>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed mb-2 font-sans">
                  {rec.reason}
                </p>

                <div className="flex items-center gap-2 text-xs font-medium bg-black/30 px-3 py-2 rounded border border-white/5 text-slate-200">
                  <strong className="text-white shrink-0 font-mono text-[11px] uppercase tracking-wide">
                    Action:
                  </strong>
                  <span>{rec.action}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
