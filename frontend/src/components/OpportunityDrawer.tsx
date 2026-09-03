"use client";

import { X, Sparkles, Shield, CheckCircle, AlertOctagon, ArrowRight } from "lucide-react";
import { useState } from "react";
import type { BrainRecommendation, Opportunity, PolicyVerdict } from "@/lib/types";
import { formatPaiseToRupees } from "@/lib/format";

interface OpportunityDrawerProps {
  opportunity: Opportunity | null;
  onClose: () => void;
  onAnalyze: (paymentId: string) => Promise<BrainRecommendation | null>;
  onExecute: (paymentId: string, action: string, recommendation?: BrainRecommendation) => Promise<{
    status: string;
    verdict?: PolicyVerdict;
    result?: Record<string, unknown>;
  } | null>;
}

export default function OpportunityDrawer({
  opportunity,
  onClose,
  onAnalyze,
  onExecute,
}: OpportunityDrawerProps) {
  const [analyzing, setAnalyzing] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [recommendation, setRecommendation] = useState<BrainRecommendation | null>(null);
  const [executionResult, setExecutionResult] = useState<{
    status: string;
    verdict?: PolicyVerdict;
    result?: Record<string, unknown>;
  } | null>(null);

  if (!opportunity) return null;

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setExecutionResult(null);
    try {
      const rec = await onAnalyze(opportunity.paymentId);
      setRecommendation(rec);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleExecute = async () => {
    const actionToRun = recommendation?.action || "PAYMENT_LINK";
    setExecuting(true);
    try {
      const res = await onExecute(opportunity.paymentId, actionToRun, recommendation ?? undefined);
      setExecutionResult(res);
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/70 backdrop-blur-sm flex justify-end">
      <div className="w-full max-w-xl bg-[#0e1117] border-l border-[#21262d] h-full overflow-y-auto flex flex-col p-6 shadow-2xl">
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-[#21262d] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold text-white">
                {opportunity.paymentId}
              </span>
              <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-zinc-800 border border-zinc-700 rounded text-zinc-300">
                {opportunity.status}
              </span>
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {formatPaiseToRupees(opportunity.amountPaise)}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-zinc-400 hover:text-white rounded-md hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Opportunity Metrics Breakdown */}
        <div className="grid grid-cols-2 gap-3 my-5">
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-md">
            <span className="text-[11px] text-zinc-400 uppercase font-mono">Recoverability Score</span>
            <div className="text-xl font-mono font-bold text-white mt-0.5">
              {Math.round(opportunity.recoverabilityScore)} / 100
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Deterministic model</div>
          </div>
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-md">
            <span className="text-[11px] text-zinc-400 uppercase font-mono text-amber-400">
              Expected Recovery (ERV)
            </span>
            <div className="text-xl font-mono font-bold text-amber-400 mt-0.5">
              {formatPaiseToRupees(opportunity.expectedRecoveryValuePaise)}
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Integer paise minor units</div>
          </div>
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-md">
            <span className="text-[11px] text-zinc-400 uppercase font-mono">Failure Category</span>
            <div className="text-sm font-medium text-zinc-200 mt-0.5 capitalize">
              {opportunity.failureCategory.replace(/_/g, " ")}
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Decline classification</div>
          </div>
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-md">
            <span className="text-[11px] text-zinc-400 uppercase font-mono">Retry History</span>
            <div className="text-sm font-mono font-medium text-zinc-200 mt-0.5">
              {opportunity.retryCount} of {opportunity.maxRetries} attempts
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Policy limits apply</div>
          </div>
        </div>

        {/* Recovery Brain AI Section */}
        <div className="border border-[#21262d] rounded-lg p-4 bg-zinc-900/40 my-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <h3 className="text-sm font-semibold text-white">Recovery Brain (Gemini Flash)</h3>
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-600/30 transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {analyzing ? "Analyzing..." : "Evaluate Opportunity"}
            </button>
          </div>

          {analyzing ? (
            <div className="py-6 text-center text-xs text-zinc-400">
              <div className="inline-block w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full animate-spin mb-1.5" />
              <div>Generating structured recommendation via Gemini API...</div>
            </div>
          ) : recommendation ? (
            <div className="space-y-3 mt-3">
              <div className="flex items-center justify-between p-2.5 bg-zinc-900 rounded border border-zinc-800">
                <span className="text-xs text-zinc-400">Recommended Bounded Action</span>
                <div className="flex flex-col items-end">
                  <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {recommendation.action}
                  </span>
                  {recommendation.action === "RETRY" && (
                    <span className="text-[9px] font-mono text-zinc-500 mt-0.5">
                      Simulated Test Action
                    </span>
                  )}
                  {recommendation.action === "PAYMENT_LINK" && (
                    <span className="text-[9px] font-mono text-blue-400 mt-0.5">
                      Razorpay Test API
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between text-xs text-zinc-400 px-1">
                <span>Model Confidence</span>
                <span className="font-mono font-medium text-zinc-200">
                  {(recommendation.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div className="p-2.5 bg-zinc-950 rounded border border-zinc-800/80 text-xs text-zinc-300 leading-relaxed">
                <span className="text-zinc-500 block text-[10px] font-mono uppercase mb-1">Reasoning Summary</span>
                {recommendation.reasoningSummary || recommendation.reason}
              </div>

              {/* Supporting & Risk Factors */}
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2 bg-zinc-900/60 rounded border border-zinc-800">
                  <span className="text-emerald-400 font-medium block mb-1">Supporting Factors</span>
                  <ul className="list-disc pl-3 text-zinc-400 space-y-0.5">
                    {recommendation.supportingFactors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
                <div className="p-2 bg-zinc-900/60 rounded border border-zinc-800">
                  <span className="text-rose-400 font-medium block mb-1">Risk Factors</span>
                  <ul className="list-disc pl-3 text-zinc-400 space-y-0.5">
                    {recommendation.riskFactors.length > 0 ? (
                      recommendation.riskFactors.map((rf, i) => <li key={i}>{rf}</li>)
                    ) : (
                      <li>No significant risk factors identified.</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-xs text-zinc-500 text-center py-4">
              Click &quot;Evaluate Opportunity&quot; to invoke the Recovery Brain with sanitized transaction context.
            </p>
          )}
        </div>

        {/* Guarded Autopilot Deterministic Policy Section */}
        <div className="border border-[#21262d] rounded-lg p-4 bg-zinc-900/40 my-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-white">Guarded Autopilot Policy</h3>
            </div>
            <span className="text-[11px] text-zinc-500 font-mono">RULES AUTHORIZE</span>
          </div>

          <p className="text-xs text-zinc-400 mb-3 leading-relaxed">
            AI recommendations cannot execute directly. Execution is strictly governed by deterministic
            eligibility, risk rules, and duplicate guards.
          </p>

          <button
            onClick={handleExecute}
            disabled={executing || opportunity.status === "captured" || opportunity.recoveryStatus === "recovered"}
            className="w-full py-2 px-4 rounded-md bg-amber-500 hover:bg-amber-400 text-black font-medium text-xs transition-colors disabled:opacity-50 flex items-center justify-center gap-2 font-mono"
          >
            {executing ? (
              "Validating & Executing..."
            ) : (
              <>
                Authorize & Execute Action
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>

          {/* Execution Result Banner */}
          {executionResult && (
            <div className="mt-3 p-3 rounded-md bg-zinc-900 border border-zinc-800 text-xs">
              {executionResult.status === "APPROVED" || executionResult.status === "EXECUTED" ? (
                <div>
                  <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                    <CheckCircle className="w-4 h-4" />
                    Action Authorized & Dispatched
                  </div>
                  <p className="text-zinc-400 text-[11px] mt-1">
                    Executed action safely in Razorpay Test Mode. Audit record recorded.
                  </p>
                </div>
              ) : executionResult.status === "BLOCKED" ? (
                <div>
                  <div className="flex items-center gap-1.5 text-rose-400 font-medium">
                    <AlertOctagon className="w-4 h-4" />
                    Action Blocked by Deterministic Policy
                  </div>
                  <p className="text-zinc-300 text-[11px] mt-1 font-mono">
                    {executionResult.verdict?.blockingReason || "Action violates risk or state rules."}
                  </p>
                </div>
              ) : (
                <div className="text-zinc-400">
                  Status: {executionResult.status}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-auto pt-4 border-t border-[#21262d] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 rounded-md transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
