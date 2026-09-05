"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical } from "lucide-react";
import Header from "@/components/Header";
import MetricsCards from "@/components/MetricsCards";
import RazorpayCheckoutView from "@/components/RazorpayCheckoutView";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { MetricSummary, ServerMessage, UserContext } from "@/lib/types";

export default function CheckoutPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserContext | null>(null);
  const [metrics, setMetrics] = useState<MetricSummary | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  const { state: connectionState, isConnected, connect, disconnect, send, on } = useWebSocket({ autoConnect: false });

  // Session verification on mount
  useEffect(() => {
    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";
    fetch(`${apiOrigin}/api/auth/me/`, { credentials: "include" })
      .then((res) => {
        if (!res.ok) {
          router.push("/login");
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (data?.authenticated && data.user) {
          setUser(data.user);
          connect();
        } else {
          router.push("/login");
        }
      })
      .catch(() => {
        router.push("/login");
      });
  }, [router, connect]);

  // Request fresh metrics
  const refreshData = useCallback(() => {
    if (isConnected) {
      send("metrics.summary", {});
    }
  }, [isConnected, send]);

  // WebSocket subscriptions for metrics
  useEffect(() => {
    const unsubMetrics = on("metrics.summary.response", (msg: ServerMessage) => {
      const p = msg.payload as MetricSummary | undefined;
      if (p) setMetrics(p);
      setLoadingMetrics(false);
    });

    const unsubMetricsUpdate = on("metrics.updated", (msg: ServerMessage) => {
      const p = msg.payload as MetricSummary | undefined;
      if (p) setMetrics(p);
    });

    return () => {
      unsubMetrics();
      unsubMetricsUpdate();
    };
  }, [on]);

  useEffect(() => {
    if (isConnected) {
      refreshData();
    }
  }, [isConnected, refreshData]);

  const handleLogout = async () => {
    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";
    try {
      disconnect("Operator signed out");
      await fetch(`${apiOrigin}/api/auth/logout/`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Ignored
    }
    router.push("/login");
  };

  const handleTabChange = (tab: "radar" | "ledger" | "metrics" | "checkout") => {
    if (tab === "checkout") return;
    router.push(`/?tab=${tab}`);
  };

  return (
    <div className="min-h-screen bg-[#070b16] text-[#f0f6fc] flex flex-col overflow-x-hidden">
      <Header
        activeTab="checkout"
        setActiveTab={handleTabChange}
        connectionState={connectionState}
        user={user}
        onLogout={handleLogout}
        onRefresh={refreshData}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 min-w-0 overflow-x-hidden">
        {/* Section Header: PAYMENTS & Test Mode card */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-2">
          <div>
            <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-500 font-medium mb-1">
              PAYMENTS
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Secure Payments for Revenue Recovery
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-2xl">
              Process test transactions through Razorpay while securely verifying server-side payment signatures and recording verified outcomes.
            </p>
          </div>

          {/* Compact Test Mode card */}
          <div className="shrink-0 bg-[#091021] border border-[#1b263b] rounded-xl p-3.5 flex items-center justify-between gap-4 max-w-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
                <FlaskConical className="w-5 h-5" />
              </div>
              <div>
                <div className="text-xs font-semibold text-white">
                  Test Mode
                </div>
                <div className="text-[11px] text-zinc-400 leading-tight mt-0.5">
                  You are using Razorpay Test Mode. No real money will be charged.
                </div>
              </div>
            </div>
            <span className="shrink-0 px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30">
              TEST MODE
            </span>
          </div>
        </div>

        {/* KPI Row */}
        <MetricsCards metrics={metrics} loading={loadingMetrics} />

        {/* Central Razorpay Checkout Card */}
        <RazorpayCheckoutView onPaymentComplete={() => refreshData()} />
      </main>
    </div>
  );
}
