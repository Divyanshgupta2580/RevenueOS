"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import MetricsCards from "@/components/MetricsCards";
import RadarTable from "@/components/RadarTable";
import OpportunityDrawer from "@/components/OpportunityDrawer";
import DecisionLedger from "@/components/DecisionLedger";
import MetricsView from "@/components/MetricsView";
import { useWebSocket } from "@/hooks/useWebSocket";
import type {
  BrainRecommendation,
  DecisionRecord,
  MetricSummary,
  Opportunity,
  PolicyVerdict,
  ServerMessage,
  UserContext,
} from "@/lib/types";

export default function CommandCenterPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"radar" | "ledger" | "metrics">("radar");
  const [user, setUser] = useState<UserContext | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  // Domain state
  const [metrics, setMetrics] = useState<MetricSummary | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null);
  const [loadingOpps, setLoadingOpps] = useState(false);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  const { state: connectionState, isConnected, request, send, on } = useWebSocket();

  // 1. Session verification on mount
  useEffect(() => {
    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://127.0.0.1:8000";
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
        }
      })
      .catch(() => {
        router.push("/login");
      })
      .finally(() => {
        setAuthChecking(false);
      });
  }, [router]);

  // 2. Request fresh data
  const refreshData = useCallback(() => {
    if (isConnected) {
      send("revenue.list", { page: 1, limit: 50 });
      send("metrics.summary", {});
    }
  }, [isConnected, send]);

  // 3. Subscribe to real-time WebSocket events
  useEffect(() => {
    const unsubList = on("revenue.list.response", (msg: ServerMessage) => {
      const p = msg.payload as { opportunities?: Opportunity[] } | undefined;
      setOpportunities(p?.opportunities || []);
      setLoadingOpps(false);
    });

    const unsubMetrics = on("metrics.summary.response", (msg: ServerMessage) => {
      const p = msg.payload as MetricSummary | undefined;
      if (p) setMetrics(p);
      setLoadingMetrics(false);
    });

    const unsubMetricsUpdate = on("metrics.updated", (msg: ServerMessage) => {
      const p = msg.payload as MetricSummary | undefined;
      if (p) setMetrics(p);
    });

    const unsubRevUpdated = on("revenue.updated", () => {
      refreshData();
    });

    const unsubPaymentUpdated = on("payment.updated", () => {
      refreshData();
    });

    return () => {
      unsubList();
      unsubMetrics();
      unsubMetricsUpdate();
      unsubRevUpdated();
      unsubPaymentUpdated();
    };
  }, [on, refreshData]);

  // 4. Initial fetch on connect
  useEffect(() => {
    if (isConnected) {
      refreshData();
    }
  }, [isConnected, refreshData]);

  // 5. Logout
  const handleLogout = async () => {
    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://127.0.0.1:8000";
    try {
      await fetch(`${apiOrigin}/api/auth/logout/`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Ignored
    }
    router.push("/login");
  };

  // 6. Gemini Recovery Brain invocation
  const handleAnalyzeOpportunity = async (paymentId: string): Promise<BrainRecommendation | null> => {
    try {
      const resp = await request<{ paymentId: string }, { recommendation?: BrainRecommendation }>(
        "recovery.analyze",
        { paymentId },
        12000
      );
      return resp.payload?.recommendation || null;
    } catch {
      return null;
    }
  };

  // 7. Guarded Autopilot execution
  const handleExecuteOpportunity = async (
    paymentId: string,
    action: string,
    recommendation?: BrainRecommendation
  ): Promise<{ status: string; verdict?: PolicyVerdict; result?: Record<string, unknown> } | null> => {
    try {
      const resp = await request<
        { paymentId: string; action: string; aiRecommendation?: BrainRecommendation },
        Record<string, unknown>
      >(
        "recovery.execute",
        { paymentId, action, aiRecommendation: recommendation },
        12000
      );

      const msgType = resp.type;
      const payload = resp.payload || {};

      if (msgType === "recovery.blocked") {
        const verdict: PolicyVerdict = {
          status: "BLOCKED",
          blockingRule: (payload.blockingRule as string) || "POLICY_RULE",
          blockingReason: (payload.blockingReason as string) || "Action blocked by policy.",
          rulesEvaluated: [],
          evaluatedAt: new Date().toISOString(),
        };
        setDecisions((prev) => [
          {
            decisionId: (payload.decisionId as string) || `dec_${Date.now()}`,
            paymentId,
            modelVersion: (payload.modelVersion as string) || "gemini-3.8-flash",
            aiRecommendation: recommendation || {
              action: "RETRY",
              confidence: 0.8,
              expectedRecoveryValuePaise: 0,
              reason: "Evaluated",
              supportingFactors: [],
              riskFactors: [],
              reasoningSummary: "",
            },
            policyDecision: verdict,
            createdAt: new Date().toISOString(),
          },
          ...prev,
        ]);
        return { status: "BLOCKED", verdict };
      }

      // Approved / Executed
      const verdict: PolicyVerdict = {
        status: "APPROVED",
        authorizedAction: action,
        rulesEvaluated: [],
        evaluatedAt: new Date().toISOString(),
      };

      setDecisions((prev) => [
        {
          decisionId: (payload.decisionId as string) || `dec_${Date.now()}`,
          paymentId,
          modelVersion: (payload.modelVersion as string) || "gemini-3.8-flash",
          aiRecommendation: recommendation || {
            action: action as "RETRY" | "PAYMENT_LINK" | "REMINDER" | "STOP",
            confidence: 0.9,
            expectedRecoveryValuePaise: 0,
            reason: "Authorized by Guarded Autopilot",
            supportingFactors: [],
            riskFactors: [],
            reasoningSummary: "",
          },
          policyDecision: verdict,
          createdAt: new Date().toISOString(),
        },
        ...prev,
      ]);

      refreshData();
      return { status: "APPROVED", verdict, result: payload };
    } catch {
      return { status: "ERROR" };
    }
  };

  if (authChecking) {
    return (
      <div className="min-h-screen bg-[#08090b] flex items-center justify-center text-zinc-400 text-xs">
        <div className="inline-block w-5 h-5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin mr-2" />
        Authenticating operator session...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#08090b] text-[#f0f6fc] flex flex-col">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        connectionState={connectionState}
        user={user}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6">
        {/* Top KPI Metrics Banner */}
        <MetricsCards metrics={metrics} loading={loadingMetrics} />

        {/* Tab 1: Revenue Radar */}
        {activeTab === "radar" && (
          <RadarTable
            opportunities={opportunities}
            loading={loadingOpps}
            onSelectOpportunity={(opp) => setSelectedOpp(opp)}
            onRefresh={refreshData}
          />
        )}

        {/* Tab 2: Decision Ledger */}
        {activeTab === "ledger" && (
          <DecisionLedger
            decisions={decisions}
            loading={false}
          />
        )}

        {/* Tab 3: Outcome Metrics */}
        {activeTab === "metrics" && (
          <MetricsView metrics={metrics} />
        )}

        {/* Opportunity Detail Drawer */}
        <OpportunityDrawer
          opportunity={selectedOpp}
          onClose={() => setSelectedOpp(null)}
          onAnalyze={handleAnalyzeOpportunity}
          onExecute={handleExecuteOpportunity}
        />
      </main>
    </div>
  );
}
