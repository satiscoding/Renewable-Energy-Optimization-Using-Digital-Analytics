"use client";

import React from "react";
import { Sun, Thermometer, Wind, Compass, CloudSun } from "lucide-react";
import { WeatherSnapshot } from "@/lib/types";

interface WeatherStripProps {
  siteType: "solar" | "wind";
  weather: WeatherSnapshot | null;
}

export const WeatherStrip: React.FC<WeatherStripProps> = ({ siteType, weather }) => {
  if (!weather) return null;

  return (
    <div className="glass-panel p-4 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
      <div className="flex items-center gap-2 text-slate-400">
        <CloudSun className="w-4 h-4 text-amber-400" />
        <span className="font-semibold text-slate-300 uppercase tracking-wider text-[11px]">
          Site Ambient Conditions
        </span>
      </div>

      <div className="flex items-center flex-wrap gap-6">
        {siteType === "solar" ? (
          <>
            <div className="flex items-center gap-2">
              <Sun className="w-4 h-4 text-amber-400" />
              <span className="text-slate-400">Irradiation:</span>
              <strong className="text-slate-200">
                {weather.irradiation !== null && weather.irradiation !== undefined
                  ? `${(weather.irradiation * 1000).toFixed(0)} W/m² (${weather.irradiation.toFixed(3)} kW/m²)`
                  : "--"}
              </strong>
            </div>

            <div className="flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-red-400" />
              <span className="text-slate-400">PV Module Temp:</span>
              <strong className="text-slate-200">
                {weather.module_temp !== null && weather.module_temp !== undefined
                  ? `${weather.module_temp.toFixed(1)} °C`
                  : "--"}
              </strong>
            </div>

            <div className="flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-slate-400" />
              <span className="text-slate-400">Ambient Temp:</span>
              <strong className="text-slate-200">
                {weather.ambient_temp !== null && weather.ambient_temp !== undefined
                  ? `${weather.ambient_temp.toFixed(1)} °C`
                  : "--"}
              </strong>
            </div>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <Wind className="w-4 h-4 text-cyan-400" />
              <span className="text-slate-400">Anemometer Wind Speed:</span>
              <strong className="text-cyan-300">
                {weather.wind_speed !== null && weather.wind_speed !== undefined
                  ? `${weather.wind_speed.toFixed(1)} m/s`
                  : "--"}
              </strong>
            </div>

            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-slate-400" />
              <span className="text-slate-400">Yaw Wind Direction:</span>
              <strong className="text-slate-200">
                {weather.wind_direction !== null && weather.wind_direction !== undefined
                  ? `${weather.wind_direction.toFixed(0)}°`
                  : "--"}
              </strong>
            </div>

            <div className="flex items-center gap-2">
              <Thermometer className="w-4 h-4 text-slate-400" />
              <span className="text-slate-400">Nacelle Ambient Temp:</span>
              <strong className="text-slate-200">
                {weather.ambient_temp !== null && weather.ambient_temp !== undefined
                  ? `${weather.ambient_temp.toFixed(1)} °C`
                  : "18.5 °C"}
              </strong>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
