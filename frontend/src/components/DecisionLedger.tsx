"use client";

import { useState } from "react";
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
} from "lucide-react";
import type { DecisionRecord } from "@/lib/types";
import { formatIsoDate, formatPaiseToRupees } from "@/lib/format";

interface ExplanationData {
  summary?: string;
  decisionFactors?: string[];
  counterfactuals?: string[];
  policyAlignment?: string;
  confidenceAssessment?: string;
}

interface DecisionLedgerProps {
  decisions: DecisionRecord[];
  loading: boolean;
  onExplain?: (decisionId: string) => Promise<ExplanationData | null>;
}

export default function DecisionLedger({ decisions, loading, onExplain }: DecisionLedgerProps) {
  const [selectedDecision, setSelectedDecision] = useState<DecisionRecord | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState<ExplanationData | null>(null);

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
      setExplanation({ summary: "Failed to generate explanation." });
    } finally {
      setExplaining(false);
    }
  };

  return (
    <div className="bg-[#0e1117] border border-[#21262d] rounded-lg overflow-hidden my-6">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[#21262d] flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Decision Ledger &amp; Audit Timeline
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Immutable audit record of all AI recommendations, policy verdicts, and authorized executions.
          </p>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="py-16 text-center text-zinc-400 text-sm">
          <div className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-2" />
          <div>Loading decision audit trail...</div>
        </div>
      ) : decisions.length === 0 ? (
        /* Truthful Empty State (Absolute No-Dummy-Data Requirement) */
        <div className="py-20 px-6 text-center">
          <div className="w-12 h-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-500">
            <FileText className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">No decision records yet</h3>
          <p className="text-xs text-zinc-500 max-w-md mx-auto mt-1.5 leading-relaxed">
            When the Recovery Brain analyzes opportunities and passes through Guarded Autopilot,
            every decision and rule breakdown will be recorded in this immutable audit ledger.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#21262d] bg-zinc-900/50 text-zinc-400 uppercase font-mono text-[10px] tracking-wider">
                <th className="py-3 px-4 font-medium">Timestamp</th>
                <th className="py-3 px-4 font-medium">Decision ID</th>
                <th className="py-3 px-4 font-medium">Payment ID</th>
                <th className="py-3 px-4 font-medium">AI Action</th>
                <th className="py-3 px-4 font-medium">Confidence</th>
                <th className="py-3 px-4 font-medium">Expected Recovery</th>
                <th className="py-3 px-4 font-medium">Policy Result</th>
                <th className="py-3 px-4 font-medium">Reason / Rule</th>
                <th className="py-3 px-4 font-medium text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#21262d]">
              {decisions.map((d) => {
                const isApproved = d.policyDecision?.status === "APPROVED";
                return (
                  <tr
                    key={d.decisionId}
                    onClick={() => handleOpenDetail(d)}
                    className="hover:bg-zinc-800/30 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4 font-mono text-zinc-400 whitespace-nowrap">
                      {formatIsoDate(d.createdAt)}
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-300 font-medium">
                      {d.decisionId}
                    </td>
                    <td className="py-3 px-4 font-mono text-white">
                      {d.paymentId}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-0.5">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30 w-max">
                          {d.aiRecommendation?.action || "RETRY"}
                        </span>
                        {d.aiRecommendation?.action === "RETRY" ? (
                          <span className="text-[9px] font-mono text-zinc-500">
                            Simulated Test Action
                          </span>
                        ) : d.aiRecommendation?.action === "PAYMENT_LINK" ? (
                          <span className="text-[9px] font-mono text-blue-400">
                            Razorpay Test API
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-300">
                      {d.aiRecommendation?.confidence
                        ? `${(d.aiRecommendation.confidence * 100).toFixed(0)}%`
                        : "-"}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-amber-400 whitespace-nowrap">
                      {typeof d.aiRecommendation?.expectedRecoveryValuePaise === "number"
                        ? formatPaiseToRupees(d.aiRecommendation.expectedRecoveryValuePaise)
                        : "-"}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${
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
                    <td className="py-3 px-4 text-zinc-400 max-w-xs truncate text-[11px]">
                      {d.policyDecision?.blockingReason || d.aiRecommendation?.reason || "Rules passed."}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(d);
                        }}
                        className="text-xs font-medium text-blue-400 group-hover:text-blue-300 inline-flex items-center gap-1"
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

      {/* Decision Detail & Explainability Modal */}
      {selectedDecision && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-[#091021] border border-[#1b263b] rounded-xl shadow-2xl p-6 max-h-[90vh] overflow-y-auto space-y-5">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#162033] pb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400">
                  <BrainCircuit className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white tracking-tight">
                    Decision Audit: {selectedDecision.decisionId}
                  </h3>
                  <p className="text-xs text-zinc-400 font-mono mt-0.5">
                    Target: {selectedDecision.paymentId} &bull; Model: {selectedDecision.modelVersion || "gemini-3.6-flash"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedDecision(null)}
                className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Decision Summary Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="bg-[#050812] border border-[#162133] rounded-lg p-3">
                <span className="text-[10px] font-mono uppercase text-zinc-400 block">Recommended Action</span>
                <span className="text-xs font-mono font-bold text-amber-300 mt-1 block">
                  {selectedDecision.aiRecommendation?.action || "RETRY"}
                </span>
              </div>
              <div className="bg-[#050812] border border-[#162133] rounded-lg p-3">
                <span className="text-[10px] font-mono uppercase text-zinc-400 block">Confidence</span>
                <span className="text-xs font-mono font-bold text-white mt-1 block">
                  {selectedDecision.aiRecommendation?.confidence
                    ? `${(selectedDecision.aiRecommendation.confidence * 100).toFixed(0)}%`
                    : "N/A"}
                </span>
              </div>
              <div className="bg-[#050812] border border-[#162133] rounded-lg p-3">
                <span className="text-[10px] font-mono uppercase text-zinc-400 block">Expected Recovery</span>
                <span className="text-xs font-mono font-bold text-amber-400 mt-1 block">
                  {typeof selectedDecision.aiRecommendation?.expectedRecoveryValuePaise === "number"
                    ? formatPaiseToRupees(selectedDecision.aiRecommendation.expectedRecoveryValuePaise)
                    : "₹0.00"}
                </span>
              </div>
              <div className="bg-[#050812] border border-[#162133] rounded-lg p-3">
                <span className="text-[10px] font-mono uppercase text-zinc-400 block">Policy Verdict</span>
                <span
                  className={`text-xs font-mono font-bold mt-1 block ${
                    selectedDecision.policyDecision?.status === "APPROVED"
                      ? "text-emerald-400"
                      : "text-rose-400"
                  }`}
                >
                  {selectedDecision.policyDecision?.status || "EVALUATED"}
                </span>
              </div>
            </div>

            {/* Why This Action / Primary Reason */}
            <div className="bg-[#050812] border border-[#162133] rounded-lg p-4 space-y-2">
              <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider font-mono flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-blue-400" />
                Why This Action
              </span>
              <p className="text-xs text-zinc-300 leading-relaxed font-sans">
                {selectedDecision.aiRecommendation?.reasoningSummary ||
                  selectedDecision.aiRecommendation?.reason ||
                  "Heuristic evaluation passed policy criteria."}
              </p>
            </div>

            {/* Supporting Factors & Risk Factors */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="bg-[#050812] border border-[#162133] rounded-lg p-3.5">
                <span className="text-xs font-semibold text-emerald-400 font-mono block mb-2">
                  Supporting Factors
                </span>
                {selectedDecision.aiRecommendation?.supportingFactors &&
                selectedDecision.aiRecommendation.supportingFactors.length > 0 ? (
                  <ul className="list-disc pl-4 space-y-1 text-xs text-zinc-300">
                    {selectedDecision.aiRecommendation.supportingFactors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-xs text-zinc-500">None specified.</span>
                )}
              </div>

              <div className="bg-[#050812] border border-[#162133] rounded-lg p-3.5">
                <span className="text-xs font-semibold text-rose-400 font-mono block mb-2">
                  Risk Factors
                </span>
                {selectedDecision.aiRecommendation?.riskFactors &&
                selectedDecision.aiRecommendation.riskFactors.length > 0 ? (
                  <ul className="list-disc pl-4 space-y-1 text-xs text-zinc-300">
                    {selectedDecision.aiRecommendation.riskFactors.map((rf, i) => (
                      <li key={i}>{rf}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-xs text-zinc-500">No elevated risk factors detected.</span>
                )}
              </div>
            </div>

            {/* Deterministic Policy Checks */}
            <div className="bg-[#050812] border border-[#162133] rounded-lg p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white font-mono flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-teal-400" />
                  Deterministic Policy Checks
                </span>
                <span className="text-[10px] font-mono text-zinc-400">
                  {selectedDecision.policyDecision?.status === "APPROVED" ? "Passed All Rules" : "Rule Blocked"}
                </span>
              </div>
              {selectedDecision.policyDecision?.blockingReason && (
                <div className="p-2.5 rounded bg-rose-950/30 border border-rose-500/30 text-xs font-mono text-rose-300">
                  Blocking Reason: {selectedDecision.policyDecision.blockingReason}
                </div>
              )}
            </div>

            {/* Gemini 3.6 Flash Deep Explanation Section */}
            <div className="bg-[#080d1c] border border-purple-500/30 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-bold text-white tracking-tight">
                    AI Decision Explanation (Gemini 3.6 Flash)
                  </span>
                </div>
                {onExplain && !explanation && (
                  <button
                    onClick={() => handleRequestExplanation(selectedDecision.decisionId)}
                    disabled={explaining}
                    className="px-3 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/40 rounded text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    {explaining ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Generating Explanation...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3 h-3" />
                        Explain Decision
                      </>
                    )}
                  </button>
                )}
              </div>

              {explanation ? (
                <div className="space-y-2 text-xs text-zinc-300 leading-relaxed font-sans animate-in fade-in">
                  <p className="p-2.5 bg-[#050812] border border-[#162133] rounded">
                    {explanation.summary}
                  </p>
                  {explanation.policyAlignment && (
                    <div className="p-2 bg-[#050812] border border-[#162133] rounded text-[11px] text-zinc-400">
                      <span className="font-semibold text-teal-400 block mb-0.5">Policy Alignment</span>
                      {explanation.policyAlignment}
                    </div>
                  )}
                  {explanation.confidenceAssessment && (
                    <div className="p-2 bg-[#050812] border border-[#162133] rounded text-[11px] text-zinc-400">
                      <span className="font-semibold text-blue-400 block mb-0.5">Confidence Assessment</span>
                      {explanation.confidenceAssessment}
                    </div>
                  )}
                </div>
              ) : !explaining ? (
                <p className="text-[11px] text-zinc-400">
                  Request a structured post-decision explanation from Gemini 3.6 Flash breaking down the factual evidence and counterfactuals.
                </p>
              ) : null}
            </div>

            {/* Modal Actions */}
            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedDecision(null)}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-xs font-semibold transition-colors"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
