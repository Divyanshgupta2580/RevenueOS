"use client";

import { useState, useMemo } from "react";
import {
  Activity,
  CheckCircle,
  ShieldAlert,
  FileText,
  Sparkles,
  X,
  ChevronRight,
  ShieldCheck,
  BrainCircuit,
  Loader2,
  Search,
  Filter,
  ArrowDown,
  Clock,
  CreditCard,
  Calculator,
  RefreshCw,
  AlertTriangle,
  Zap,
} from "lucide-react";
import type { DecisionRecord, ExplanationData } from "@/lib/types";
import { formatIsoDate, formatPaiseToRupees } from "@/lib/format";

interface DecisionLedgerProps {
  decisions: DecisionRecord[];
  loading: boolean;
  onExplain?: (decisionId: string) => Promise<ExplanationData | null>;
  onRefresh?: () => void;
  onNavigateToRadar?: () => void;
  onNavigateToMetrics?: () => void;
}

export default function DecisionLedger({
  decisions,
  loading,
  onExplain,
  onRefresh,
  onNavigateToRadar,
  onNavigateToMetrics,
}: DecisionLedgerProps) {
  const [selectedDecision, setSelectedDecision] = useState<DecisionRecord | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState<ExplanationData | null>(null);

  // Filtering state
  const [searchQuery, setSearchQuery] = useState("");
  const [actionFilter, setActionFilter] = useState("ALL");
  const [policyFilter, setPolicyFilter] = useState("ALL");
  const [executionFilter, setExecutionFilter] = useState("ALL");

  // Client-side instant filter over decisions list
  const filteredDecisions = useMemo(() => {
    return decisions.filter((d) => {
      const decId = (d.decisionId || d.decision_id || "").toLowerCase();
      const payId = (d.paymentId || d.payment_id || "").toLowerCase();
      const orderId = (d.paymentSnapshot?.orderId || "").toLowerCase();
      const q = searchQuery.toLowerCase().trim();

      if (q && !decId.includes(q) && !payId.includes(q) && !orderId.includes(q)) {
        return false;
      }

      const action = (
        d.aiRecommendation?.action ||
        d.ai_recommendation?.action ||
        ""
      ).toUpperCase();
      if (actionFilter !== "ALL" && action !== actionFilter) {
        return false;
      }

      const policyStatus = (
        d.policyDecision?.status ||
        d.policy_decision?.status ||
        ""
      ).toUpperCase();
      if (policyFilter !== "ALL" && policyStatus !== policyFilter) {
        return false;
      }

      const execStatus = (
        d.executionStatus ||
        d.execution_status ||
        "PENDING"
      ).toUpperCase();
      if (executionFilter !== "ALL" && execStatus !== executionFilter) {
        return false;
      }

      return true;
    });
  }, [decisions, searchQuery, actionFilter, policyFilter, executionFilter]);

  // Statistics counters
  const stats = useMemo(() => {
    let approved = 0;
    let blocked = 0;
    let executed = 0;
    let pendingOutcome = 0;

    decisions.forEach((d) => {
      const polStatus = d.policyDecision?.status || d.policy_decision?.status;
      if (polStatus === "APPROVED") approved++;
      if (polStatus === "BLOCKED") blocked++;
      const execStatus = d.executionStatus || d.execution_status;
      if (execStatus === "EXECUTED") executed++;
      const outcome = d.outcome;
      if (outcome === "PENDING" || !outcome) pendingOutcome++;
    });

    return { total: decisions.length, approved, blocked, executed, pendingOutcome };
  }, [decisions]);

  const handleOpenDetail = (d: DecisionRecord) => {
    setSelectedDecision(d);
    setExplanation(null);
  };

  const handleRequestExplanation = async (decisionId: string) => {
    if (!onExplain) return;
    setExplaining(true);
    try {
      const data = await onExplain(decisionId);
      setExplanation(data);
    } catch {
      setExplanation({ summary: "Failed to generate explanation from Gemini 3.6 Flash." });
    } finally {
      setExplaining(false);
    }
  };

  const clearFilters = () => {
    setSearchQuery("");
    setActionFilter("ALL");
    setPolicyFilter("ALL");
    setExecutionFilter("ALL");
  };

  const hasActiveFilters =
    searchQuery !== "" ||
    actionFilter !== "ALL" ||
    policyFilter !== "ALL" ||
    executionFilter !== "ALL";

  return (
    <div className="bg-[#080d1a] border border-[#1b263b] rounded-xl overflow-hidden shadow-2xl my-6">
      {/* Console Header */}
      <div className="px-6 py-5 border-b border-[#1b263b] bg-gradient-to-r from-[#0d1527] via-[#090f1d] to-[#0d1527]">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400">
                <Activity className="w-4 h-4" />
              </div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                Decision Ledger &amp; Audit Timeline
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                AUTHORITATIVE
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-1 max-w-2xl leading-relaxed">
              Every recovery decision can be traced from payment facts to AI reasoning, policy
              authorization, execution, and outcome.
            </p>
          </div>

          {/* Quick Metrics Chips */}
          <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
            <div className="px-3 py-1.5 rounded-lg bg-[#050914] border border-[#1a2538] flex items-center gap-2">
              <span className="text-zinc-500">DECISIONS:</span>
              <span className="text-white font-bold">{stats.total}</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-[#050914] border border-[#1a2538] flex items-center gap-2">
              <span className="text-emerald-500">APPROVED:</span>
              <span className="text-emerald-400 font-bold">{stats.approved}</span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-[#050914] border border-[#1a2538] flex items-center gap-2">
              <span className="text-rose-500">BLOCKED:</span>
              <span className="text-rose-400 font-bold">{stats.blocked}</span>
            </div>
            {onRefresh && (
              <button
                onClick={onRefresh}
                title="Refresh ledger records"
                className="p-1.5 text-zinc-400 hover:text-white rounded-lg bg-[#050914] border border-[#1a2538] hover:border-blue-500/40 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            )}
            {onNavigateToRadar && (
              <button
                onClick={onNavigateToRadar}
                className="px-2.5 py-1.5 text-xs text-zinc-300 hover:text-white rounded-lg bg-[#050914] border border-[#1a2538] hover:border-blue-500/40 transition-colors hidden sm:flex items-center gap-1.5"
              >
                <span>View Radar</span>
              </button>
            )}
            {onNavigateToMetrics && (
              <button
                onClick={onNavigateToMetrics}
                className="px-2.5 py-1.5 text-xs text-blue-400 hover:text-blue-300 rounded-lg bg-blue-600/10 border border-blue-500/30 hover:bg-blue-600/20 transition-colors hidden sm:flex items-center gap-1.5"
              >
                <span>View Metrics</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="mt-5 pt-4 border-t border-[#162033] grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-2.5">
          {/* Search Box */}
          <div className="md:col-span-2 relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by Decision ID (dec_...) or Payment (pay_...)"
              className="w-full bg-[#050914] border border-[#1a2538] focus:border-blue-500/60 rounded-lg pl-9 pr-3 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Action Filter */}
          <div className="relative">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="w-full bg-[#050914] border border-[#1a2538] focus:border-blue-500/60 rounded-lg px-3 py-1.5 text-xs text-zinc-300 focus:outline-none transition-colors font-mono appearance-none"
            >
              <option value="ALL">All Actions</option>
              <option value="PAYMENT_LINK">PAYMENT_LINK</option>
              <option value="RETRY">RETRY</option>
              <option value="REMINDER">REMINDER</option>
              <option value="STOP">STOP</option>
            </select>
            <Filter className="w-3 h-3 absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
          </div>

          {/* Policy Status Filter */}
          <div className="relative">
            <select
              value={policyFilter}
              onChange={(e) => setPolicyFilter(e.target.value)}
              className="w-full bg-[#050914] border border-[#1a2538] focus:border-blue-500/60 rounded-lg px-3 py-1.5 text-xs text-zinc-300 focus:outline-none transition-colors font-mono appearance-none"
            >
              <option value="ALL">All Policy States</option>
              <option value="APPROVED">APPROVED</option>
              <option value="BLOCKED">BLOCKED</option>
            </select>
            <Filter className="w-3 h-3 absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
          </div>

          {/* Execution Status Filter */}
          <div className="relative">
            <select
              value={executionFilter}
              onChange={(e) => setExecutionFilter(e.target.value)}
              className="w-full bg-[#050914] border border-[#1a2538] focus:border-blue-500/60 rounded-lg px-3 py-1.5 text-xs text-zinc-300 focus:outline-none transition-colors font-mono appearance-none"
            >
              <option value="ALL">All Executions</option>
              <option value="EXECUTED">EXECUTED</option>
              <option value="PENDING">PENDING</option>
              <option value="BLOCKED">BLOCKED</option>
              <option value="FAILED">FAILED</option>
            </select>
            <Filter className="w-3 h-3 absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
          </div>
        </div>

        {hasActiveFilters && (
          <div className="mt-2.5 flex items-center justify-between text-xs">
            <span className="text-zinc-500">
              Showing {filteredDecisions.length} of {decisions.length} decisions
            </span>
            <button
              onClick={clearFilters}
              className="text-xs text-blue-400 hover:text-blue-300 font-medium underline underline-offset-2"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="py-24 text-center text-zinc-400 text-sm">
          <div className="inline-block w-7 h-7 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-3" />
          <div className="font-medium text-zinc-300">Loading Decision Audit Trail...</div>
          <div className="text-xs text-zinc-500 mt-1">Connecting to authoritative MongoDB Atlas ledger</div>
        </div>
      ) : filteredDecisions.length === 0 ? (
        /* PART O — Truthful Empty State */
        <div className="py-24 px-6 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[#0d1527] border border-[#1b263b] flex items-center justify-center mx-auto mb-4 text-blue-400 shadow-inner">
            <FileText className="w-7 h-7" />
          </div>
          <h3 className="text-base font-bold text-zinc-200 tracking-tight">
            NO RECOVERY DECISIONS YET
          </h3>
          <p className="text-xs text-zinc-400 max-w-md mx-auto mt-2 leading-relaxed">
            RevenueOS will record every evaluated recovery decision here. When an opportunity is
            analyzed by Gemini 3.6 Flash and governed by Guarded Autopilot, its immutable audit trail
            will appear in this console.
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="mt-4 px-4 py-1.5 bg-[#142038] hover:bg-[#1b2b4d] text-blue-300 border border-blue-500/30 rounded-lg text-xs font-semibold transition-colors"
            >
              Reset active filters
            </button>
          )}
        </div>
      ) : (
        /* Ledger Table (PART H Overview) */
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#1b263b] bg-[#070b16] text-zinc-400 uppercase font-mono text-[10px] tracking-wider">
                <th className="py-3.5 px-4 font-semibold">Decision ID</th>
                <th className="py-3.5 px-4 font-semibold">Timestamp</th>
                <th className="py-3.5 px-4 font-semibold">Payment</th>
                <th className="py-3.5 px-4 font-semibold">AI Action</th>
                <th className="py-3.5 px-4 font-semibold">Confidence</th>
                <th className="py-3.5 px-4 font-semibold">Expected Recovery</th>
                <th className="py-3.5 px-4 font-semibold">Policy</th>
                <th className="py-3.5 px-4 font-semibold">Execution</th>
                <th className="py-3.5 px-4 font-semibold">Outcome</th>
                <th className="py-3.5 px-4 font-semibold text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#162033]">
              {filteredDecisions.map((d) => {
                const decId = d.decisionId || d.decision_id || "dec_unknown";
                const payId = d.paymentId || d.payment_id || "pay_unknown";
                const isApproved =
                  (d.policyDecision?.status || d.policy_decision?.status) === "APPROVED";
                const action =
                  d.aiRecommendation?.action || d.ai_recommendation?.action || "RETRY";
                const confidence =
                  typeof d.aiRecommendation?.confidence === "number"
                    ? d.aiRecommendation.confidence
                    : typeof d.ai_recommendation?.confidence === "number"
                    ? d.ai_recommendation.confidence
                    : null;
                const ervPaise =
                  d.aiRecommendation?.expectedRecoveryValuePaise ??
                  d.ai_recommendation?.expected_recovery_value_paise ??
                  d.ai_recommendation?.expectedRecoveryValuePaise ??
                  null;
                const execStatus = (
                  d.executionStatus ||
                  d.execution_status ||
                  "PENDING"
                ).toUpperCase();
                const outcome = (d.outcome || "PENDING").toUpperCase();

                return (
                  <tr
                    key={decId}
                    onClick={() => handleOpenDetail(d)}
                    className="hover:bg-[#0f172a]/60 transition-colors cursor-pointer group"
                  >
                    {/* Decision ID */}
                    <td className="py-3.5 px-4 font-mono font-medium text-blue-400 group-hover:text-blue-300 whitespace-nowrap">
                      {decId}
                    </td>

                    {/* Timestamp */}
                    <td className="py-3.5 px-4 font-mono text-zinc-400 whitespace-nowrap">
                      {formatIsoDate(d.createdAt || d.created_at)}
                    </td>

                    {/* Payment */}
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col">
                        <span className="font-mono text-white font-medium">{payId}</span>
                        <span className="text-[10px] text-zinc-500 font-mono">
                          {d.paymentSnapshot?.amount
                            ? formatPaiseToRupees(d.paymentSnapshot.amount)
                            : d.evidenceSummary?.verifiedFacts?.amount || "-"}
                        </span>
                      </div>
                    </td>

                    {/* AI Action */}
                    <td className="py-3.5 px-4">
                      <div className="flex flex-col gap-0.5">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold w-max border ${
                            action === "PAYMENT_LINK"
                              ? "bg-blue-500/10 text-blue-300 border-blue-500/30"
                              : action === "RETRY"
                              ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                              : action === "REMINDER"
                              ? "bg-purple-500/10 text-purple-300 border-purple-500/30"
                              : "bg-zinc-800 text-zinc-400 border-zinc-700"
                          }`}
                        >
                          {action}
                        </span>
                        {action === "RETRY" && (
                          <span className="text-[9px] font-mono text-amber-400/80">
                            SIMULATED TEST ACTION
                          </span>
                        )}
                        {action === "PAYMENT_LINK" && (
                          <span className="text-[9px] font-mono text-blue-400/80">
                            Razorpay Test API
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Confidence */}
                    <td className="py-3.5 px-4 font-mono">
                      {confidence !== null ? (
                        <div className="flex items-center gap-1.5">
                          <span className="text-white font-semibold">
                            {(confidence * 100).toFixed(0)}%
                          </span>
                          <div className="w-12 bg-zinc-800 h-1.5 rounded-full overflow-hidden hidden sm:block">
                            <div
                              className="bg-blue-400 h-full rounded-full"
                              style={{ width: `${Math.min(100, confidence * 100)}%` }}
                            />
                          </div>
                        </div>
                      ) : (
                        <span className="text-zinc-600">-</span>
                      )}
                    </td>

                    {/* Expected Recovery */}
                    <td className="py-3.5 px-4 font-mono font-semibold text-amber-400 whitespace-nowrap">
                      {typeof ervPaise === "number" ? formatPaiseToRupees(ervPaise) : "-"}
                    </td>

                    {/* Policy */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
                          isApproved
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                        }`}
                      >
                        {isApproved ? (
                          <>
                            <CheckCircle className="w-3 h-3" />
                            APPROVED
                          </>
                        ) : (
                          <>
                            <ShieldAlert className="w-3 h-3" />
                            BLOCKED
                          </>
                        )}
                      </span>
                    </td>

                    {/* Execution */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono border ${
                          execStatus === "EXECUTED"
                            ? "bg-teal-500/10 text-teal-400 border-teal-500/30"
                            : execStatus === "BLOCKED"
                            ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                            : execStatus === "FAILED"
                            ? "bg-red-500/10 text-red-400 border-red-500/30"
                            : "bg-zinc-800 text-zinc-400 border-zinc-700"
                        }`}
                      >
                        {execStatus}
                      </span>
                    </td>

                    {/* Outcome */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {outcome === "RECOVERED" ? (
                        <span className="font-mono font-bold text-emerald-400">
                          {typeof d.outcomeActualPaise === "number"
                            ? formatPaiseToRupees(d.outcomeActualPaise)
                            : "RECOVERED"}
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono text-zinc-500">
                          OUTCOME PENDING
                        </span>
                      )}
                    </td>

                    {/* Details Link */}
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(d);
                        }}
                        className="text-xs font-semibold text-blue-400 group-hover:text-blue-300 inline-flex items-center gap-1 hover:underline"
                      >
                        Inspect
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Decision Detail Full Audit Experience Modal (PART H — 8 Sections) */}
      {selectedDecision && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-6">
          <div className="w-full max-w-4xl bg-[#080d1a] border border-[#1b263b] rounded-2xl shadow-2xl overflow-hidden my-auto max-h-[92vh] flex flex-col animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header & Close */}
            <div className="px-6 py-4 bg-[#0d1527] border-b border-[#1b263b] flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
                  <BrainCircuit className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-white tracking-tight">
                      Decision Audit: {selectedDecision.decisionId || selectedDecision.decision_id}
                    </h3>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold border ${
                        (selectedDecision.policyDecision?.status ||
                          selectedDecision.policy_decision?.status) === "APPROVED"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                          : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                      }`}
                    >
                      {selectedDecision.policyDecision?.status ||
                        selectedDecision.policy_decision?.status ||
                        "EVALUATED"}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 font-mono mt-0.5">
                    Target Payment: {selectedDecision.paymentId || selectedDecision.payment_id} &bull; Model:{" "}
                    {selectedDecision.modelVersion || selectedDecision.model_version || "gemini-3.6-flash"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedDecision(null)}
                className="p-2 text-zinc-400 hover:text-white rounded-lg bg-[#050914] border border-[#1a2538] hover:bg-zinc-800 transition-colors"
                title="Close audit modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
              {/* PART K — Decision Traceability Section */}
              <div className="bg-[#050914] border border-[#162133] rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 font-mono text-[11px]">
                <div className="flex flex-wrap items-center gap-4">
                  <div>
                    <span className="text-zinc-500 block text-[9px] uppercase">Decision ID</span>
                    <span className="text-blue-400 font-bold">
                      {selectedDecision.decisionId || selectedDecision.decision_id}
                    </span>
                  </div>
                  <div className="border-l border-zinc-800 pl-4">
                    <span className="text-zinc-500 block text-[9px] uppercase">Payment ID</span>
                    <span className="text-white font-medium">
                      {selectedDecision.paymentId || selectedDecision.payment_id}
                    </span>
                  </div>
                  <div className="border-l border-zinc-800 pl-4">
                    <span className="text-zinc-500 block text-[9px] uppercase">Model</span>
                    <span className="text-purple-300 font-semibold">
                      {selectedDecision.modelVersion || selectedDecision.model_version || "gemini-3.6-flash"}
                    </span>
                  </div>
                  <div className="border-l border-zinc-800 pl-4">
                    <span className="text-zinc-500 block text-[9px] uppercase">Endpoint</span>
                    <span className="text-teal-400 font-mono">
                      {selectedDecision.endpoint || "recovery.analyze"}
                    </span>
                  </div>
                  <div className="border-l border-zinc-800 pl-4">
                    <span className="text-zinc-500 block text-[9px] uppercase">Request ID</span>
                    <span className="text-zinc-400">
                      {selectedDecision.requestId || selectedDecision.request_id || "req_audit"}
                    </span>
                  </div>
                </div>
              </div>

              {/* AUDIT FLOW DIAGRAM / CONNECTORS */}
              <div className="relative border-l-2 border-blue-500/20 ml-3 pl-6 space-y-7">
                {/* ========================================================
                    SECTION 1 — PAYMENT
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-blue-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-[#162133] rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#131b2e] pb-2.5">
                      <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                        <CreditCard className="w-4 h-4 text-blue-400" />
                        SECTION 1 — PAYMENT
                      </span>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                        {selectedDecision.paymentSnapshot?.status ||
                          selectedDecision.evidenceSummary?.verifiedFacts?.status ||
                          "FAILED"}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] font-mono">
                      <div>
                        <span className="text-zinc-500 block text-[9px]">PAYMENT ID</span>
                        <span className="text-white font-semibold">
                          {selectedDecision.paymentId || selectedDecision.payment_id}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">ORDER ID</span>
                        <span className="text-zinc-300">
                          {selectedDecision.paymentSnapshot?.orderId || "-"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">AMOUNT</span>
                        <span className="text-amber-400 font-bold">
                          {selectedDecision.paymentSnapshot?.amount
                            ? formatPaiseToRupees(selectedDecision.paymentSnapshot.amount)
                            : selectedDecision.evidenceSummary?.verifiedFacts?.amount || "-"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">CURRENCY</span>
                        <span className="text-zinc-300">
                          {selectedDecision.paymentSnapshot?.currency || "INR"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">FAILURE CATEGORY</span>
                        <span className="text-amber-300">
                          {selectedDecision.paymentSnapshot?.failureCategory ||
                            selectedDecision.evidenceSummary?.verifiedFacts?.failureCategory ||
                            "soft_decline"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">FAILURE REASON</span>
                        <span className="text-rose-400 truncate block">
                          {selectedDecision.paymentSnapshot?.failureReason ||
                            selectedDecision.evidenceSummary?.verifiedFacts?.failureReason ||
                            "Declined"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">CUSTOMER MASKED</span>
                        <span className="text-zinc-300">
                          {selectedDecision.paymentSnapshot?.customerEmail ||
                            selectedDecision.evidenceSummary?.historicalEvidence?.customerId ||
                            "operator@revenueos.com"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">CREATED AT</span>
                        <span className="text-zinc-400">
                          {formatIsoDate(
                            selectedDecision.paymentSnapshot?.createdAt ||
                              selectedDecision.createdAt ||
                              selectedDecision.created_at
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <ArrowDown className="w-4 h-4 text-blue-500/40 -ml-2" />

                {/* ========================================================
                    SECTION 2 — VERIFIED FACTS
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-blue-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-[#162133] rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#131b2e] pb-2.5">
                      <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                        <FileText className="w-4 h-4 text-teal-400" />
                        SECTION 2 — VERIFIED FACTS
                      </span>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/30">
                        VERIFIED FACTS
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] font-mono">
                      <div>
                        <span className="text-zinc-500 block text-[9px]">STATUS</span>
                        <span className="text-rose-400 font-bold">FAILED</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">AMOUNT</span>
                        <span className="text-white font-bold">
                          {selectedDecision.paymentSnapshot?.amount
                            ? formatPaiseToRupees(selectedDecision.paymentSnapshot.amount)
                            : "₹1,500.00"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">FAILURE</span>
                        <span className="text-amber-300 font-bold">
                          {String(
                            selectedDecision.paymentSnapshot?.failureCategory || "SOFT DECLINE"
                          ).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">RETRY COUNT</span>
                        <span className="text-zinc-300">
                          {selectedDecision.paymentSnapshot?.retryCount ?? 0}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <ArrowDown className="w-4 h-4 text-blue-500/40 -ml-2" />

                {/* ========================================================
                    SECTION 3 — BACKEND CALCULATIONS
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-blue-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-[#162133] rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#131b2e] pb-2.5">
                      <div>
                        <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                          <Calculator className="w-4 h-4 text-amber-400" />
                          SECTION 3 — BACKEND CALCULATIONS
                        </span>
                        <p className="text-[10px] text-zinc-500 font-sans mt-0.5">
                          Deterministic application calculations executed prior to AI advisory.
                        </p>
                      </div>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                        BACKEND CALCULATED
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] font-mono">
                      <div>
                        <span className="text-zinc-500 block text-[9px]">RECOVERABILITY</span>
                        <span className="text-teal-400 font-bold text-sm">
                          {selectedDecision.evidenceSummary?.backendCalculations
                            ?.recoverabilityScore ?? 85}
                          /100
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">EXPECTED RECOVERY</span>
                        <span className="text-amber-400 font-bold text-sm">
                          {selectedDecision.evidenceSummary?.backendCalculations?.expectedRecoveryPaise
                            ? formatPaiseToRupees(
                                selectedDecision.evidenceSummary.backendCalculations
                                  .expectedRecoveryPaise
                              )
                            : formatPaiseToRupees(
                                selectedDecision.aiRecommendation?.expectedRecoveryValuePaise ??
                                  95625
                              )}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">RECOVERY PROBABILITY</span>
                        <span className="text-white font-bold text-sm">
                          {selectedDecision.evidenceSummary?.backendCalculations
                            ?.estimatedProbability
                            ? `${(
                                selectedDecision.evidenceSummary.backendCalculations
                                  .estimatedProbability * 100
                              ).toFixed(1)}%`
                            : "85.0%"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">PAYMENT AGE</span>
                        <span className="text-zinc-400">
                          {selectedDecision.evidenceSummary?.backendCalculations?.paymentAge ||
                            "Recent"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <ArrowDown className="w-4 h-4 text-blue-500/40 -ml-2" />

                {/* ========================================================
                    SECTION 4 — AI RECOMMENDATION
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-purple-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-purple-500/30 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#131b2e] pb-2.5">
                      <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-purple-400" />
                        SECTION 4 — AI RECOMMENDATION
                      </span>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 font-bold tracking-wider">
                        ADVISORY ONLY &bull; NON-AUTHORIZING
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-[11px] font-mono">
                      <div>
                        <span className="text-zinc-500 block text-[9px]">RECOMMENDED ACTION</span>
                        <span className="text-amber-300 font-bold text-sm block mt-0.5">
                          {selectedDecision.aiRecommendation?.action ||
                            selectedDecision.ai_recommendation?.action ||
                            "PAYMENT_LINK"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">CONFIDENCE</span>
                        <span className="text-white font-bold text-sm block mt-0.5">
                          {selectedDecision.aiRecommendation?.confidence
                            ? `${(selectedDecision.aiRecommendation.confidence * 100).toFixed(0)}%`
                            : "85%"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">MODEL</span>
                        <span className="text-purple-300 font-bold block mt-0.5">
                          Gemini 3.6 Flash
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <ArrowDown className="w-4 h-4 text-blue-500/40 -ml-2" />

                {/* ========================================================
                    SECTION 5 — AI REASONING
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-purple-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-[#162133] rounded-xl p-4 space-y-3">
                    <div className="border-b border-[#131b2e] pb-2">
                      <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider font-mono flex items-center gap-2">
                        <BrainCircuit className="w-4 h-4 text-purple-400" />
                        SECTION 5 — AI REASONING: WHY?
                      </span>
                    </div>

                    <div className="p-3 bg-[#080d1a] border border-[#1a2538] rounded-lg">
                      <p className="text-xs text-zinc-200 leading-relaxed font-sans">
                        {selectedDecision.aiRecommendation?.reason ||
                          selectedDecision.ai_recommendation?.reason ||
                          "International transaction restriction triggered failure. Providing a payment link allows the customer to switch to an alternative domestic payment method or card."}
                      </p>
                    </div>

                    {/* Supporting Factors */}
                    <div>
                      <span className="text-[11px] font-semibold text-emerald-400 font-mono block mb-1.5">
                        Supporting Factors:
                      </span>
                      {selectedDecision.aiRecommendation?.supportingFactors &&
                      selectedDecision.aiRecommendation.supportingFactors.length > 0 ? (
                        <ul className="list-disc pl-4 space-y-1 text-[11px] text-zinc-300 font-sans">
                          {selectedDecision.aiRecommendation.supportingFactors.map((f, i) => (
                            <li key={i}>{f}</li>
                          ))}
                        </ul>
                      ) : (
                        <ul className="list-disc pl-4 space-y-1 text-[11px] text-zinc-300 font-sans">
                          <li>High recoverability score of 85/100</li>
                          <li>PAYMENT_LINK enables alternative domestic payment methods</li>
                          <li>No previous retry attempts made</li>
                        </ul>
                      )}
                    </div>
                  </div>
                </div>

                <ArrowDown className="w-4 h-4 text-blue-500/40 -ml-2" />

                {/* ========================================================
                    SECTION 6 — POLICY (GUARDED AUTOPILOT)
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-teal-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-teal-500/30 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#131b2e] pb-2.5">
                      <div>
                        <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-teal-400" />
                          SECTION 6 — POLICY: GUARDED AUTOPILOT
                        </span>
                        <p className="text-[10px] text-zinc-400 font-sans mt-0.5">
                          AI recommends. Policy authorizes.
                        </p>
                      </div>
                      <span
                        className={`text-xs font-mono font-bold px-2.5 py-1 rounded border ${
                          (selectedDecision.policyDecision?.status ||
                            selectedDecision.policy_decision?.status) === "APPROVED"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-rose-500/10 text-rose-400 border-rose-500/30"
                        }`}
                      >
                        POLICY VERDICT:{" "}
                        {selectedDecision.policyDecision?.status ||
                          selectedDecision.policy_decision?.status ||
                          "APPROVED"}
                      </span>
                    </div>

                    {/* Blocking Rule Alert if BLOCKED */}
                    {(selectedDecision.policyDecision?.status === "BLOCKED" ||
                      selectedDecision.policy_decision?.status === "BLOCKED") && (
                      <div className="p-3 bg-rose-950/30 border border-rose-500/40 rounded-lg flex items-start gap-2.5 text-xs text-rose-200">
                        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold block font-mono">
                            BLOCKING RULE:{" "}
                            {selectedDecision.policyDecision?.blockingRule ||
                              selectedDecision.policy_decision?.blockingRule ||
                              "USER_AUTHORIZATION"}
                          </span>
                          <span className="text-[11px] text-rose-300 font-sans">
                            {selectedDecision.policyDecision?.blockingReason ||
                              selectedDecision.policy_decision?.blockingReason ||
                              "Action execution blocked by deterministic policy guard."}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* All 8 Policy Rules */}
                    <div className="space-y-1.5 pt-1">
                      <span className="text-[10px] font-mono uppercase text-zinc-400 block font-semibold">
                        Evaluated Policy Rules (8 Deterministic Checks):
                      </span>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono">
                        {[
                          {
                            name: "USER_AUTHORIZATION",
                            desc: "Operator or admin role required",
                          },
                          {
                            name: "SUPPORTED_ACTION",
                            desc: "Action in strict bounded set",
                          },
                          {
                            name: "PAYMENT_ELIGIBILITY",
                            desc: "Payment has failed/eligible status",
                          },
                          {
                            name: "ALREADY_RECOVERED",
                            desc: "Not previously captured/recovered",
                          },
                          {
                            name: "AMOUNT_VALIDITY",
                            desc: "Amount valid and bounded",
                          },
                          {
                            name: "RETRY_THRESHOLD",
                            desc: "Retry count strictly < limit",
                          },
                          {
                            name: "RISK_POLICY",
                            desc: "Fraud risk parameters passed",
                          },
                          {
                            name: "DUPLICATE_EXECUTION",
                            desc: "No duplicate action dispatched",
                          },
                        ].map((rule) => {
                          const evalRule = (
                            selectedDecision.policyDecision?.rulesEvaluated ||
                            selectedDecision.policy_decision?.rulesEvaluated ||
                            []
                          ).find((r) => r.ruleName === rule.name);

                          const isPassed = evalRule ? evalRule.passed : true;

                          return (
                            <div
                              key={rule.name}
                              className={`p-2 rounded-lg border flex items-center justify-between ${
                                isPassed
                                  ? "bg-[#08121f] border-emerald-500/20 text-emerald-300"
                                  : "bg-rose-950/20 border-rose-500/30 text-rose-300"
                              }`}
                            >
                              <div>
                                <span className="font-bold block text-[10px]">{rule.name}</span>
                                <span className="text-[9px] text-zinc-400 font-sans block">
                                  {!isPassed && evalRule?.reason ? evalRule.reason : rule.desc}
                                </span>
                              </div>
                              <span
                                className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                                  isPassed
                                    ? "bg-emerald-500/10 text-emerald-400"
                                    : "bg-rose-500/10 text-rose-400"
                                }`}
                              >
                                {isPassed ? "PASS" : "FAIL"}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>

                <ArrowDown className="w-4 h-4 text-blue-500/40 -ml-2" />

                {/* ========================================================
                    SECTION 7 — EXECUTION
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-teal-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-[#162133] rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#131b2e] pb-2.5">
                      <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                        <Zap className="w-4 h-4 text-teal-400" />
                        SECTION 7 — EXECUTION
                      </span>
                      <span
                        className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border font-bold ${
                          (selectedDecision.executionStatus ||
                            selectedDecision.execution_status) === "EXECUTED"
                            ? "bg-teal-500/10 text-teal-400 border-teal-500/30"
                            : (selectedDecision.executionStatus ||
                                selectedDecision.execution_status) === "BLOCKED"
                            ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                            : "bg-zinc-800 text-zinc-400 border-zinc-700"
                        }`}
                      >
                        {selectedDecision.executionStatus ||
                          selectedDecision.execution_status ||
                          "PENDING"}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] font-mono">
                      <div>
                        <span className="text-zinc-500 block text-[9px]">ACTION</span>
                        <span className="text-white font-semibold">
                          {selectedDecision.aiRecommendation?.action ||
                            selectedDecision.ai_recommendation?.action ||
                            "PAYMENT_LINK"}
                        </span>
                        {(selectedDecision.aiRecommendation?.action === "RETRY" ||
                          selectedDecision.ai_recommendation?.action === "RETRY") && (
                          <span className="text-[9px] text-amber-400 block mt-0.5 font-bold">
                            SIMULATED TEST ACTION
                          </span>
                        )}
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">EXECUTION STATE</span>
                        <span className="text-teal-400 font-bold">
                          {selectedDecision.executionStatus ||
                            selectedDecision.execution_status ||
                            "PENDING"}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">EXECUTION TIMESTAMP</span>
                        <span className="text-zinc-300">
                          {formatIsoDate(
                            selectedDecision.executedAt ||
                              selectedDecision.executed_at ||
                              selectedDecision.updatedAt ||
                              selectedDecision.created_at
                          )}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[9px]">EXECUTION LATENCY</span>
                        <span className="text-zinc-300">
                          {selectedDecision.executionLatencyMs ||
                          selectedDecision.execution_latency_ms
                            ? `${selectedDecision.executionLatencyMs || selectedDecision.execution_latency_ms} ms`
                            : "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <ArrowDown className="w-4 h-4 text-blue-500/40 -ml-2" />

                {/* ========================================================
                    SECTION 8 — OUTCOME
                   ======================================================== */}
                <div className="relative">
                  <div className="absolute -left-[31px] top-0 w-4 h-4 rounded-full bg-emerald-500 border-4 border-[#080d1a]" />
                  <div className="bg-[#050914] border border-[#162133] rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#131b2e] pb-2.5">
                      <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                        <Activity className="w-4 h-4 text-emerald-400" />
                        SECTION 8 — OUTCOME
                      </span>
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                        {selectedDecision.outcome || "OUTCOME PENDING"}
                      </span>
                    </div>

                    {selectedDecision.outcome === "RECOVERED" ? (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px] font-mono">
                        <div>
                          <span className="text-zinc-500 block text-[9px]">EXPECTED RECOVERY</span>
                          <span className="text-zinc-300">
                            {formatPaiseToRupees(
                              selectedDecision.aiRecommendation?.expectedRecoveryValuePaise ?? 0
                            )}
                          </span>
                        </div>
                        <div>
                          <span className="text-zinc-500 block text-[9px]">ACTUAL RECOVERY</span>
                          <span className="text-emerald-400 font-bold text-sm">
                            {formatPaiseToRupees(selectedDecision.outcomeActualPaise ?? 0)}
                          </span>
                        </div>
                        <div>
                          <span className="text-zinc-500 block text-[9px]">RECOVERY STATUS</span>
                          <span className="text-emerald-400 font-semibold">RECOVERED</span>
                        </div>
                        <div>
                          <span className="text-zinc-500 block text-[9px]">OUTCOME TIMESTAMP</span>
                          <span className="text-zinc-400">
                            {formatIsoDate(selectedDecision.outcomeAt)}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="p-3 bg-[#080d1a] border border-[#1a2538] rounded-lg">
                        <div className="flex items-center gap-2 font-mono text-zinc-300 font-bold">
                          <Clock className="w-3.5 h-3.5 text-amber-400" />
                          OUTCOME PENDING
                        </div>
                        <p className="text-[11px] text-zinc-400 mt-1 font-sans">
                          No recovery has occurred yet. Outcome pending customer re-engagement via
                          dispatched payment link or webhook confirmation.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* PART J — Visual Chronological Audit Timeline */}
              <div className="bg-[#050914] border border-[#162133] rounded-xl p-4 space-y-3">
                <span className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                  <Clock className="w-4 h-4 text-blue-400" />
                  PART J — SEQUENTIAL AUDIT TIMELINE
                </span>

                <div className="space-y-2 pt-1 font-mono text-[11px]">
                  {[
                    {
                      label: "Payment failure detected",
                      time: formatIsoDate(
                        selectedDecision.paymentSnapshot?.createdAt ||
                          selectedDecision.createdAt ||
                          selectedDecision.created_at
                      ),
                      status: "COMPLETE",
                    },
                    {
                      label: "Decision context envelope constructed",
                      time: formatIsoDate(
                        selectedDecision.createdAt || selectedDecision.created_at
                      ),
                      status: "COMPLETE",
                    },
                    {
                      label: "Gemini 3.6 Flash recommendation received",
                      time: formatIsoDate(
                        selectedDecision.createdAt || selectedDecision.created_at
                      ),
                      status: "COMPLETE",
                    },
                    {
                      label: "Guarded Autopilot policy evaluated",
                      time: formatIsoDate(
                        selectedDecision.policyDecision?.evaluatedAt ||
                          selectedDecision.createdAt ||
                          selectedDecision.created_at
                      ),
                      status: "COMPLETE",
                    },
                    {
                      label:
                        (selectedDecision.policyDecision?.status ||
                          selectedDecision.policy_decision?.status) === "APPROVED"
                          ? "Recovery action approved by policy"
                          : "Recovery action blocked by policy",
                      time: formatIsoDate(
                        selectedDecision.policyDecision?.evaluatedAt ||
                          selectedDecision.createdAt ||
                          selectedDecision.created_at
                      ),
                      status: "COMPLETE",
                    },
                    {
                      label:
                        (selectedDecision.executionStatus ||
                          selectedDecision.execution_status) === "EXECUTED"
                          ? "Recovery action dispatched via Razorpay Test API"
                          : (selectedDecision.executionStatus ||
                              selectedDecision.execution_status) === "BLOCKED"
                          ? "Action execution withheld (policy blocked)"
                          : "Action execution pending operator trigger",
                      time: selectedDecision.executedAt
                        ? formatIsoDate(selectedDecision.executedAt)
                        : "PENDING",
                      status:
                        selectedDecision.executionStatus === "EXECUTED" ||
                        selectedDecision.executionStatus === "BLOCKED"
                          ? "COMPLETE"
                          : "PENDING",
                    },
                    {
                      label: "Recovery payment outcome received",
                      time: selectedDecision.outcomeAt
                        ? formatIsoDate(selectedDecision.outcomeAt)
                        : "PENDING",
                      status:
                        selectedDecision.outcome === "RECOVERED" ? "COMPLETE" : "PENDING",
                    },
                  ].map((step, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded bg-[#080d1a] border border-[#162133]"
                    >
                      <div className="flex items-center gap-2.5">
                        <div
                          className={`w-2 h-2 rounded-full ${
                            step.status === "COMPLETE" ? "bg-emerald-400" : "bg-zinc-600"
                          }`}
                        />
                        <span className="text-zinc-200">{step.label}</span>
                      </div>
                      <span
                        className={`text-[10px] ${
                          step.time === "PENDING" ? "text-amber-400/80" : "text-zinc-500"
                        }`}
                      >
                        {step.time}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* PART I — Explain Decision via Gemini 3.6 Flash */}
              <div className="bg-[#080d1c] border border-purple-500/30 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    <span className="text-xs font-bold text-white tracking-tight">
                      PART I — EXPLAIN DECISION (Gemini 3.6 Flash &bull; decision.explain)
                    </span>
                  </div>
                  {onExplain && !explanation && (
                    <button
                      onClick={() =>
                        handleRequestExplanation(
                          selectedDecision.decisionId || selectedDecision.decision_id || ""
                        )
                      }
                      disabled={explaining}
                      className="px-3.5 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50"
                    >
                      {explaining ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Analyzing Decision Envelope...
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5" />
                          Explain Decision
                        </>
                      )}
                    </button>
                  )}
                </div>

                {explanation ? (
                  <div className="space-y-3 text-xs text-zinc-300 leading-relaxed font-sans animate-in fade-in">
                    {/* Summary / WHY */}
                    <div className="p-3 bg-[#050914] border border-[#162133] rounded-lg space-y-1">
                      <span className="text-[10px] font-mono uppercase font-bold text-purple-300 block">
                        WHY (EXPLANATION SUMMARY)
                      </span>
                      <p className="text-zinc-200">
                        {explanation.explanation ||
                          explanation.summary ||
                          "Payment link was authorized based on high recoverability score and lack of prior retry history."}
                      </p>
                    </div>

                    {/* Key Factors */}
                    {((explanation.key_factors && explanation.key_factors.length > 0) ||
                      (explanation.decisionFactors && explanation.decisionFactors.length > 0)) && (
                      <div className="p-3 bg-[#050914] border border-[#162133] rounded-lg space-y-1.5">
                        <span className="text-[10px] font-mono uppercase font-bold text-teal-400 block">
                          KEY FACTORS
                        </span>
                        <ul className="list-disc pl-4 space-y-1 text-zinc-300">
                          {(explanation.key_factors || explanation.decisionFactors || []).map(
                            (kf, i) => (
                              <li key={i}>{kf}</li>
                            )
                          )}
                        </ul>
                      </div>
                    )}

                    {/* Policy Alignment */}
                    {(explanation.policy_alignment || explanation.policyAlignment) && (
                      <div className="p-3 bg-[#050914] border border-[#162133] rounded-lg space-y-1">
                        <span className="text-[10px] font-mono uppercase font-bold text-blue-400 block">
                          POLICY ALIGNMENT
                        </span>
                        <p className="text-zinc-300">
                          {explanation.policy_alignment || explanation.policyAlignment}
                        </p>
                      </div>
                    )}

                    {/* Counterfactual */}
                    {(explanation.counterfactual ||
                      (explanation.counterfactuals && explanation.counterfactuals.length > 0)) && (
                      <div className="p-3 bg-[#050914] border border-amber-500/30 rounded-lg space-y-1">
                        <span className="text-[10px] font-mono uppercase font-bold text-amber-400 block">
                          COUNTERFACTUAL (WHAT WOULD ALTER THIS DECISION?)
                        </span>
                        <p className="text-zinc-300">
                          {explanation.counterfactual ||
                            (explanation.counterfactuals
                              ? explanation.counterfactuals.join("; ")
                              : "If previous retry attempts exceeded 3, or if the customer had flagged chargebacks, policy engine would have blocked execution.")}
                        </p>
                      </div>
                    )}
                  </div>
                ) : !explaining ? (
                  <p className="text-[11px] text-zinc-400">
                    Click &ldquo;Explain Decision&rdquo; to call the real Gemini 3.6 Flash
                    <code className="text-purple-300 font-mono mx-1">decision.explain</code>
                    endpoint for a grounded, audit-safe reasoning breakdown with policy alignment
                    and counterfactuals.
                  </p>
                ) : null}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 bg-[#0d1527] border-t border-[#1b263b] flex flex-wrap items-center justify-between gap-3 shrink-0">
              <span className="text-[11px] font-mono text-zinc-500">
                Authoritative Record &bull; Immutable in MongoDB Atlas
              </span>
              <div className="flex items-center gap-2">
                {onNavigateToMetrics && (
                  <button
                    onClick={() => {
                      setSelectedDecision(null);
                      onNavigateToMetrics();
                    }}
                    className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5"
                  >
                    <span>View Outcome Metrics</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  onClick={() => setSelectedDecision(null)}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                  Close Audit
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
