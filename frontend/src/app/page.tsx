"use client";

import React, { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Header } from "@/components/Header";
import { SiteSelector } from "@/components/SiteSelector";
import { PrimaryStatusCard } from "@/components/PrimaryStatusCard";
import { OutputHistoryChart } from "@/components/OutputHistoryChart";
import { ForecastChart } from "@/components/ForecastChart";
import { RecommendationsPanel } from "@/components/RecommendationsPanel";
import { WeatherStrip } from "@/components/WeatherStrip";
import {
  fetchSites,
  fetchSiteStatus,
  fetchSiteHistory,
  fetchSiteForecasts,
  fetchSiteRecommendations
} from "@/lib/api";
import { Site, SiteStatus, HistoryResponse, ForecastResponse, RecommendationItem } from "@/lib/types";

function DashboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<string>("");
  const [status, setStatus] = useState<SiteStatus | null>(null);
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);

  const [loadingStatus, setLoadingStatus] = useState<boolean>(true);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(true);
  const [loadingForecast, setLoadingForecast] = useState<boolean>(true);
  const [loadingRecs, setLoadingRecs] = useState<boolean>(true);

  // 1. Initial sites load and URL synchronization
  useEffect(() => {
    async function loadSites() {
      try {
        const fetchedSites = await fetchSites();
        setSites(fetchedSites);

        const urlSiteId = searchParams.get("siteId");
        if (urlSiteId && fetchedSites.some((s) => s.id === urlSiteId)) {
          setSelectedSiteId(urlSiteId);
        } else if (fetchedSites.length > 0) {
          setSelectedSiteId(fetchedSites[0].id);
          router.replace(`/?siteId=${encodeURIComponent(fetchedSites[0].id)}`);
        }
      } catch (err) {
        console.error("Failed to load sites:", err);
      }
    }
    loadSites();
  }, [searchParams, router]);

  // Handle site selection
  const handleSelectSite = (siteId: string) => {
    setSelectedSiteId(siteId);
    router.replace(`/?siteId=${encodeURIComponent(siteId)}`);
  };

  // 2. Data fetching for active site
  const loadAllDataForSite = useCallback(async (siteId: string, isInitial: boolean = false) => {
    if (!siteId) return;

    if (isInitial) {
      setLoadingStatus(true);
      setLoadingHistory(true);
      setLoadingForecast(true);
      setLoadingRecs(true);
    }

    try {
      // Parallel fetch for speed
      const [statusRes, historyRes, forecastRes, recsRes] = await Promise.allSettled([
        fetchSiteStatus(siteId),
        fetchSiteHistory(siteId, 24),
        fetchSiteForecasts(siteId, 6),
        fetchSiteRecommendations(siteId, "active")
      ]);

      if (statusRes.status === "fulfilled") setStatus(statusRes.value);
      if (historyRes.status === "fulfilled") setHistory(historyRes.value);
      if (forecastRes.status === "fulfilled") setForecast(forecastRes.value);
      if (recsRes.status === "fulfilled") setRecommendations(recsRes.value);
    } catch (err) {
      console.error("Error updating site telemetry:", err);
    } finally {
      if (isInitial) {
        setLoadingStatus(false);
        setLoadingHistory(false);
        setLoadingForecast(false);
        setLoadingRecs(false);
      }
    }
  }, []);

  // Trigger load when selectedSiteId changes
  useEffect(() => {
    if (selectedSiteId) {
      loadAllDataForSite(selectedSiteId, true);
    }
  }, [selectedSiteId, loadAllDataForSite]);

  // 3. Auto-refresh polling every 6 seconds
  useEffect(() => {
    if (!selectedSiteId) return;

    const interval = setInterval(() => {
      loadAllDataForSite(selectedSiteId, false);
    }, 6000);

    return () => clearInterval(interval);
  }, [selectedSiteId, loadAllDataForSite]);

  const activeSite = sites.find((s) => s.id === selectedSiteId);

  return (
    <div className="min-h-screen flex flex-col bg-[#090D16]">
      <Header
        currentSiteId={selectedSiteId}
        onRefresh={() => loadAllDataForSite(selectedSiteId, false)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-6 space-y-6">
        
        {/* Navigation & Site Selection Row */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <SiteSelector
            sites={sites}
            selectedSiteId={selectedSiteId}
            onSelectSite={handleSelectSite}
          />
          <div className="text-xs text-slate-400 font-mono">
            Auto-refreshing every 6s • Active Site: <strong className="text-white">{activeSite?.name || selectedSiteId}</strong>
          </div>
        </div>

        {/* Primary Status & KPI Card */}
        <PrimaryStatusCard
          status={status}
          loading={loadingStatus}
        />

        {/* Ambient Weather Strip */}
        <WeatherStrip
          siteType={activeSite?.type || "solar"}
          weather={status?.latest_weather || null}
        />

        {/* Dual Chart Grid: Trailing History & Future Forecast */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="h-[380px]">
            <OutputHistoryChart
              history={history}
              loading={loadingHistory}
            />
          </div>

          <div className="h-[380px]">
            <ForecastChart
              forecast={forecast}
              loading={loadingForecast}
            />
          </div>
        </div>

        {/* Actionable Recommendations Panel */}
        <div className="w-full">
          <RecommendationsPanel
            recommendations={recommendations}
            loading={loadingRecs}
          />
        </div>

      </main>

      <footer className="border-t border-white/5 py-4 text-center text-xs text-slate-500 font-mono">
        Renewable Energy Optimization Control Room • Phase-II B.Tech Final Year Project • Powered by FastAPI & Next.js
      </footer>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-400 font-mono">Loading Control Room Dashboard...</div>}>
      <DashboardContent />
    </Suspense>
  );
}
