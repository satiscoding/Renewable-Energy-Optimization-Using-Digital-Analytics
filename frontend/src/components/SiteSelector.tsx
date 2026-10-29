"use client";

import React from "react";
import { Sun, Wind } from "lucide-react";
import { Site } from "@/lib/types";

interface SiteSelectorProps {
  sites: Site[];
  selectedSiteId: string;
  onSelectSite: (siteId: string) => void;
}

export const SiteSelector: React.FC<SiteSelectorProps> = ({
  sites,
  selectedSiteId,
  onSelectSite,
}) => {
  return (
    <div className="flex items-center gap-3 p-1.5 bg-slate-900/60 backdrop-blur-md border border-white/10 rounded-xl w-fit">
      {sites.map((site) => {
        const isSelected = site.id === selectedSiteId;
        const isSolar = site.type === "solar";

        return (
          <button
            key={site.id}
            onClick={() => onSelectSite(site.id)}
            className={`flex items-center gap-2.5 px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200 relative ${
              isSelected
                ? isSolar
                  ? "bg-gradient-to-r from-amber-500/25 to-amber-600/15 border border-amber-500/50 text-amber-300 shadow-glass-amber scale-[1.02]"
                  : "bg-gradient-to-r from-cyan-500/25 to-cyan-600/15 border border-cyan-500/50 text-cyan-300 shadow-glass-cyan scale-[1.02]"
                : "text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent hover:border-white/5"
            }`}
          >
            {isSolar ? (
              <Sun className={`w-4 h-4 ${isSelected ? "text-amber-400" : "text-slate-400"}`} />
            ) : (
              <Wind className={`w-4 h-4 ${isSelected ? "text-cyan-400" : "text-slate-400"}`} />
            )}
            <span>{site.name}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-slate-300 font-mono">
              {site.capacity_kw} kW
            </span>
          </button>
        );
      })}
    </div>
  );
};
