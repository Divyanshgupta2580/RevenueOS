"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { FlaskConical } from "lucide-react";
import Header from "@/components/Header";
import MetricsCards from "@/components/MetricsCards";
import RadarTable from "@/components/RadarTable";
import OpportunityDrawer from "@/components/OpportunityDrawer";
import DecisionLedger from "@/components/DecisionLedger";
import MetricsView from "@/components/MetricsView";
import RazorpayCheckoutView from "@/components/RazorpayCheckoutView";
import { useWebSocket } from "@/hooks/useWebSocket";
import type {
  BrainRecommendation,
  DecisionRecord,
  ExplanationData,
  MetricSummary,
  Opportunity,
  PolicyVerdict,
  RuleEvaluation,
  ServerMessage,
  UserContext,
} from "@/lib/types";

export default function CommandCenterPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"radar" | "ledger" | "metrics" | "checkout">("radar");
  const [user, setUser] = useState<UserContext | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  // Domain state
  const [metrics, setMetrics] = useState<MetricSummary | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null);
  const [loadingOpps, setLoadingOpps] = useState(false);
  const [loadingMetrics, setLoadingMetrics] = useState(false);
  const [loadingDecisions, setLoadingDecisions] = useState(false);

  const { state: connectionState, isConnected, connect, disconnect, request, send, on } = useWebSocket({ autoConnect: false });

  // 1. Session verification on mount
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
      })
      .finally(() => {
        setAuthChecking(false);
      });
  }, [router, connect]);

  // 2. Request fresh data
  const refreshData = useCallback(() => {
    if (isConnected) {
      send("revenue.list", { page: 1, limit: 50 });
      send("metrics.summary", {});
      send("decision.list", { page: 1, pageSize: 50 });
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

    const unsubDecisions = on("decision.list.response", (msg: ServerMessage) => {
      const p = msg.payload as { decisions?: DecisionRecord[] } | undefined;
      if (p?.decisions) {
        setDecisions(p.decisions);
      }
      setLoadingDecisions(false);
    });

    const unsubDecisionCreated = on("decision.created", (msg: ServerMessage) => {
      const p = msg.payload as DecisionRecord | undefined;
      if (p) {
        setDecisions((prev) => [p, ...prev.filter((d) => d.decisionId !== p.decisionId)]);
      }
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
      unsubDecisions();
      unsubDecisionCreated();
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

  const inFlightAnalysesRef = useRef<Set<string>>(new Set());

  // 6. Gemini Recovery Brain invocation with real stage listener and in-flight deduplication
  const handleAnalyzeOpportunity = async (
    paymentId: string,
    onStageUpdate?: (stage: string) => void
  ): Promise<BrainRecommendation | null> => {
    if (inFlightAnalysesRef.current.has(paymentId)) {
      console.warn(`[RecoveryBrain] Analysis already in-flight for ${paymentId}; dropping duplicate request.`);
      return null;
    }
    inFlightAnalysesRef.current.add(paymentId);

    // Register real stage listener for this payment
    const unsubStage = on("analysis.stage", (msg: ServerMessage) => {
      const p = msg.payload as { paymentId?: string; stage?: string } | undefined;
      if (p && p.paymentId === paymentId && p.stage && onStageUpdate) {
        onStageUpdate(p.stage);
      }
    });

    try {
      const resp = await request<
        { paymentId: string },
        { recommendation?: BrainRecommendation; telemetry?: Record<string, number> }
      >(
        "recovery.analyze",
        { paymentId },
        35000
      );
      const rec = resp.payload?.recommendation || null;
      if (rec && resp.payload?.telemetry) {
        rec.telemetry = resp.payload.telemetry;
      }
      return rec;
    } catch (err) {
      console.error("[RecoveryBrain] Analysis request failed or timed out:", err);
      return {
        action: "STOP",
        confidence: 0.0,
        expectedRecoveryValuePaise: 0,
        reason: "AI service temporarily unavailable or request timed out.",
        supportingFactors: [],
        riskFactors: ["External service timeout or unavailable"],
        reasoningSummary: "AI service unavailable; fallback recommended.",
        is_fallback: true,
        fallback_reason: "AI SERVICE UNAVAILABLE",
      };
    } finally {
      unsubStage();
      inFlightAnalysesRef.current.delete(paymentId);
    }
  };

  // 6b. Gemini 3.6 Flash Decision Explanation
  const handleExplainDecision = async (decisionId: string): Promise<ExplanationData | null> => {
    try {
      const resp = await request<
        { decisionId: string },
        { explanation?: ExplanationData }
      >(
        "decision.explain",
        { decisionId },
        45000
      );
      return resp.payload?.explanation || null;
    } catch (err) {
      console.error("[WebSocket] handleExplainDecision error:", err);
      return null;
    }
  };

  // 7. Guarded Autopilot execution
  const handleExecuteOpportunity = async (
    paymentId: string,
    action: string,
    recommendation?: BrainRecommendation
  ): Promise<{ status: string; verdict?: PolicyVerdict; result?: Record<string, unknown>; decisionId?: string } | null> => {
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
      const rawVerdict = payload.verdict as PolicyVerdict | undefined;
      const decId = (payload.decisionId as string) || `dec_${Date.now()}`;

      if (msgType === "recovery.blocked") {
        const verdict: PolicyVerdict = {
          status: "BLOCKED",
          blockingRule: (payload.blockingRule as string) || rawVerdict?.blockingRule || "POLICY_RULE",
          blockingReason: (payload.blockingReason as string) || rawVerdict?.blockingReason || "Action blocked by policy.",
          rulesEvaluated: (payload.rulesEvaluated as RuleEvaluation[]) || rawVerdict?.rulesEvaluated || [],
          evaluatedAt: rawVerdict?.evaluatedAt || new Date().toISOString(),
        };
        setDecisions((prev) => [
          {
            decisionId: decId,
            paymentId,
            modelVersion: (payload.modelVersion as string) || "gemini-3.6-flash",
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
        return { status: "BLOCKED", verdict, result: payload, decisionId: decId };
      }

      // Approved / Executed
      const verdict: PolicyVerdict = {
        status: "APPROVED",
        authorizedAction: action,
        blockingRule: null,
        blockingReason: null,
        rulesEvaluated: (payload.rulesEvaluated as RuleEvaluation[]) || rawVerdict?.rulesEvaluated || [],
        evaluatedAt: rawVerdict?.evaluatedAt || new Date().toISOString(),
      };

      setDecisions((prev) => [
        {
          decisionId: decId,
          paymentId,
          modelVersion: (payload.modelVersion as string) || "gemini-3.6-flash",
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
      return { status: "APPROVED", verdict, result: payload, decisionId: decId };
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
    <div className="min-h-screen bg-[#070b16] text-[#f0f6fc] flex flex-col overflow-x-hidden">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        connectionState={connectionState}
        user={user}
        onLogout={handleLogout}
        onRefresh={refreshData}
      />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 py-6 min-w-0 overflow-x-hidden">
        {activeTab === "checkout" ? (
          <div>
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
          </div>
        ) : (
          <div>
            {/* Tab 1: Revenue Radar */}
            {activeTab === "radar" && (
              <RadarTable
                opportunities={opportunities}
                loading={loadingOpps}
                onSelectOpportunity={(opp) => setSelectedOpp(opp)}
                onRefresh={refreshData}
                onGoToCheckout={() => setActiveTab("checkout")}
              />
            )}

            {/* Tab 2: Decision Ledger */}
            {activeTab === "ledger" && (
              <DecisionLedger
                decisions={decisions}
                loading={loadingDecisions}
                onExplain={handleExplainDecision}
                onRefresh={refreshData}
                onNavigateToRadar={() => setActiveTab("radar")}
                onNavigateToMetrics={() => setActiveTab("metrics")}
              />
            )}

            {/* Tab 3: Outcome Metrics */}
            {activeTab === "metrics" && (
              <div className="space-y-6">
                <MetricsCards metrics={metrics} loading={loadingMetrics} />
                <MetricsView metrics={metrics} />
              </div>
            )}
          </div>
        )}

        {/* Opportunity Detail Drawer */}
        <OpportunityDrawer
          opportunity={selectedOpp}
          onClose={() => setSelectedOpp(null)}
          onAnalyze={handleAnalyzeOpportunity}
          onExecute={handleExecuteOpportunity}
          onExplain={handleExplainDecision}
          decisions={decisions}
          onInspectDecision={() => {
            setSelectedOpp(null);
            setActiveTab("ledger");
          }}
          onNavigateToMetrics={() => {
            setSelectedOpp(null);
            setActiveTab("metrics");
          }}
        />
      </main>
    </div>
  );
}
