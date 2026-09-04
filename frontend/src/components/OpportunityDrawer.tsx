"use client";

import { useState } from "react";
import {
  X,
  Sparkles,
  Shield,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  CreditCard,
  Loader2,
  ExternalLink,
  Copy,
  Check,
} from "lucide-react";
import type { BrainRecommendation, Opportunity, PolicyVerdict } from "@/lib/types";
import { formatPaiseToRupees } from "@/lib/format";
import { launchRazorpayCheckout } from "@/lib/razorpay";

interface OpportunityDrawerProps {
  opportunity: Opportunity | null;
  onClose: () => void;
  onAnalyze: (paymentId: string) => Promise<BrainRecommendation | null>;
  onExecute: (
    paymentId: string,
    action: string,
    recommendation?: BrainRecommendation
  ) => Promise<{
    status: string;
    verdict?: PolicyVerdict;
    result?: Record<string, unknown>;
  } | null>;
  onInspectDecision?: (paymentId: string) => void;
}

export default function OpportunityDrawer({
  opportunity,
  onClose,
  onAnalyze,
  onExecute,
  onInspectDecision,
}: OpportunityDrawerProps) {
  const [analyzing, setAnalyzing] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [recommendation, setRecommendation] = useState<BrainRecommendation | null>(null);
  const [executionResult, setExecutionResult] = useState<{
    status: string;
    verdict?: PolicyVerdict;
    result?: Record<string, unknown>;
  } | null>(null);
  const [checkingOut, setCheckingOut] = useState(false);
  const [checkoutMsg, setCheckoutMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [copied, setCopied] = useState(false);

  if (!opportunity) return null;

  // Determine risk level based on recoverability score
  const score = Math.round(opportunity.recoverabilityScore || 0);
  const isHighConversion = score >= 70;
  const isModerateRisk = score >= 40 && score < 70;

  // Authoritative policy status
  const isHardDecline =
    opportunity.failureCategory.toLowerCase().includes("fraud") ||
    opportunity.failureCategory.toLowerCase().includes("hard_decline") ||
    opportunity.failureCategory.toLowerCase().includes("expired") ||
    opportunity.failureCategory.toLowerCase().includes("stolen");
  const isOverRetry = opportunity.retryCount >= opportunity.maxRetries;
  const isBlocked = opportunity.policyStatus === "BLOCKED" || isHardDecline || isOverRetry;
  const isApproved = !isBlocked;

  // AI action determination
  const effectiveAiAction =
    recommendation?.action ||
    opportunity.heuristicRecommendedAction ||
    opportunity.recommendedIntervention ||
    "PAYMENT_LINK";
  const effectiveConfidence =
    recommendation?.confidence ??
    (typeof opportunity.aiConfidence === "number" ? opportunity.aiConfidence : 0.75);

  const handleCopyId = () => {
    navigator.clipboard.writeText(opportunity.paymentId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
    setExecuting(true);
    try {
      const res = await onExecute(
        opportunity.paymentId,
        effectiveAiAction,
        recommendation ?? undefined
      );
      setExecutionResult(res);
    } finally {
      setExecuting(false);
    }
  };

  const handleRazorpayModalCheckout = async () => {
    setCheckingOut(true);
    setCheckoutMsg(null);
    try {
      await launchRazorpayCheckout({
        amountPaise: opportunity.amountPaise,
        currency: "INR",
        name: "RevenueOS Recovery Checkout",
        description: `Recovery payment for ${opportunity.paymentId}`,
        paymentReference: opportunity.paymentId,
        onSuccess: (res) => {
          setCheckingOut(false);
          setCheckoutMsg({
            type: "success",
            text: `Payment ${res.payment_id} verified via HMAC-SHA256 and captured!`,
          });
        },
        onDismiss: () => {
          setCheckingOut(false);
          setCheckoutMsg({
            type: "error",
            text: "Checkout modal dismissed. Payment was cancelled.",
          });
        },
        onFailure: (err) => {
          setCheckingOut(false);
          setCheckoutMsg({
            type: "error",
            text: err.description || "Razorpay payment processing failed.",
          });
        },
      });
    } catch (err: unknown) {
      setCheckingOut(false);
      const errMsg =
        err instanceof Error ? err.message : "Failed to open Razorpay checkout modal.";
      setCheckoutMsg({
        type: "error",
        text: errMsg,
      });
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Payment Opportunity Details"
      className="fixed inset-0 z-50 overflow-hidden bg-black/75 backdrop-blur-sm flex justify-end"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-[#091021] border-l border-[#1b263b] h-full overflow-y-auto flex flex-col p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ==================================================
            1. TOP: Payment, Amount, Risk Status
            ================================================== */}
        <div className="border-b border-[#1b263b] pb-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-widest uppercase font-semibold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                COMMAND CENTER
              </span>
              <span className="text-zinc-600 text-xs">&bull;</span>
              <span className="text-xs text-zinc-400 font-mono">
                {opportunity.recoveryStatus.toUpperCase()}
              </span>
            </div>
            <button
              onClick={onClose}
              aria-label="Close drawer"
              className="p-1.5 text-zinc-400 hover:text-white rounded-lg hover:bg-zinc-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex items-baseline justify-between mt-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold text-white">
                  {opportunity.paymentId}
                </span>
                <button
                  onClick={handleCopyId}
                  title="Copy payment ID"
                  className="text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  {copied ? (
                    <Check className="w-3.5 h-3.5 text-teal-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
              <div className="text-xs text-zinc-400 mt-0.5">
                Customer:{" "}
                <span className="text-zinc-300 font-mono">
                  {opportunity.customerMasked}
                </span>
              </div>
            </div>

            <div className="text-right">
              <div className="text-2xl font-bold font-mono text-white tracking-tight">
                {formatPaiseToRupees(opportunity.amountPaise)}
              </div>
              <div className="text-[10px] font-mono text-zinc-500">
                Amount At Risk
              </div>
            </div>
          </div>

          {/* Risk status banner */}
          <div className="flex items-center gap-2 mt-3">
            {isHighConversion ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium bg-teal-500/10 text-teal-400 border border-teal-500/20">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Low Risk • High Recoverability Opportunity
              </span>
            ) : isModerateRisk ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <AlertTriangle className="w-3.5 h-3.5" />
                Elevated Risk • Bounded Intervention Required
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                <ShieldAlert className="w-3.5 h-3.5" />
                High Risk • Low Yield Opportunity
              </span>
            )}
            <span className="text-xs font-mono text-zinc-500 ml-auto">
              Order: {opportunity.orderId || "Direct"}
            </span>
          </div>
        </div>

        {/* ==================================================
            2. RECOVERABILITY & EXPECTED RECOVERY (Deterministic)
            ================================================== */}
        <div className="py-4 border-b border-[#1b263b] space-y-3">
          <div className="text-[11px] font-mono tracking-wider uppercase text-zinc-400 font-medium flex items-center justify-between">
            <span>Deterministic Financial Modeling</span>
            <span className="text-[10px] text-zinc-500">Mathematical engine</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* Recoverability Score */}
            <div className="p-3.5 rounded-xl bg-[#070b16] border border-[#1b263b]">
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span>Recoverability</span>
                <span className="text-[10px] font-mono text-zinc-500">Deterministic score</span>
              </div>
              <div className="text-xl font-bold font-mono text-white mt-1">
                {score} / 100
              </div>
              {/* Progress bar */}
              <div className="w-full bg-[#1b263b] h-1.5 rounded-full mt-2 overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    score >= 70
                      ? "bg-teal-400"
                      : score >= 40
                      ? "bg-amber-400"
                      : "bg-rose-500"
                  }`}
                  style={{ width: `${Math.max(5, Math.min(100, score))}%` }}
                />
              </div>
              <div className="text-[10px] text-zinc-500 mt-2 font-mono">
                Category: <span className="text-zinc-300 capitalize">{opportunity.failureCategory.replace(/_/g, " ")}</span>
              </div>
            </div>

            {/* Expected Recovery (ERV) */}
            <div className="p-3.5 rounded-xl bg-[#070b16] border border-[#1b263b]">
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="text-amber-400">Expected Recovery</span>
                <span className="text-[10px] font-mono text-zinc-500">Backend calculated</span>
              </div>
              <div className="text-xl font-bold font-mono text-amber-400 mt-1">
                {formatPaiseToRupees(opportunity.expectedRecoveryValuePaise)}
              </div>
              <div className="text-[10px] text-zinc-500 mt-2 font-mono leading-tight">
                Deterministic calculation: Amount &times; ({score}/100)
              </div>
              <div className="text-[10px] text-zinc-500 mt-1 font-mono">
                Attempts: <span className="text-zinc-300">{opportunity.retryCount} of {opportunity.maxRetries} used</span>
              </div>
            </div>
          </div>
        </div>

        {/* ==================================================
            3. AI RECOMMENDATION & CONFIDENCE
            ================================================== */}
        <div className="py-4 border-b border-[#1b263b] space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-blue-400" />
              <span className="text-[11px] font-mono tracking-wider uppercase text-blue-300 font-medium">
                AI Recommendation (Gemini 3.6 Flash)
              </span>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">
              Advisory only &bull; Non-authorizing
            </span>
          </div>

          <div className="p-3.5 rounded-xl bg-[#070b16] border border-blue-500/20 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs text-zinc-400 block">Recommended Intervention</span>
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono font-bold bg-blue-500/15 text-blue-300 border border-blue-500/30 mt-1">
                  <Sparkles className="w-3 h-3 text-blue-400" />
                  {effectiveAiAction.replace(/_/g, " ")}
                </span>
              </div>

              <div className="text-right">
                <span className="text-xs text-zinc-400 block">Model Confidence</span>
                <div className="text-sm font-mono font-bold text-white mt-1">
                  {Math.round(effectiveConfidence * 100)}%
                </div>
                <div className="w-20 bg-[#1b263b] h-1 rounded-full mt-1 ml-auto overflow-hidden">
                  <div
                    className="bg-blue-400 h-full rounded-full"
                    style={{ width: `${Math.round(effectiveConfidence * 100)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Live Gemini reasoning / trigger */}
            {analyzing ? (
              <div className="py-4 text-center text-xs text-zinc-400 bg-blue-950/20 rounded-lg border border-blue-500/20">
                <Loader2 className="w-4 h-4 text-blue-400 animate-spin mx-auto mb-1.5" />
                <span>Generating structured inference with Gemini 3.6 Flash...</span>
              </div>
            ) : recommendation ? (
              <div className="space-y-2.5 text-xs text-zinc-300 pt-2 border-t border-[#141d30]">
                <div className="bg-[#091021] p-2.5 rounded-lg border border-[#1b263b] leading-relaxed">
                  <span className="text-[10px] font-mono uppercase text-zinc-500 block mb-1">
                    AI Contextual Reasoning
                  </span>
                  {recommendation.reasoningSummary || recommendation.reason}
                </div>

                {recommendation.supportingFactors && recommendation.supportingFactors.length > 0 && (
                  <div className="p-2.5 rounded-lg bg-teal-950/20 border border-teal-500/20 text-[11px]">
                    <span className="font-semibold text-teal-400 block mb-1">
                      Supporting Factors
                    </span>
                    <ul className="list-disc pl-4 text-zinc-400 space-y-0.5">
                      {recommendation.supportingFactors.map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {recommendation.riskFactors && recommendation.riskFactors.length > 0 && (
                  <div className="p-2.5 rounded-lg bg-rose-950/20 border border-rose-500/20 text-[11px]">
                    <span className="font-semibold text-rose-400 block mb-1">
                      Risk Considerations
                    </span>
                    <ul className="list-disc pl-4 text-zinc-400 space-y-0.5">
                      {recommendation.riskFactors.map((rf, i) => (
                        <li key={i}>{rf}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-between pt-1 border-t border-[#141d30]">
                <span className="text-[11px] text-zinc-400">
                  Detailed contextual analysis available on demand
                </span>
                <button
                  onClick={handleAnalyze}
                  className="px-3 py-1 text-xs font-mono font-medium rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 transition-colors inline-flex items-center gap-1.5"
                >
                  <Sparkles className="w-3 h-3 text-blue-400" />
                  Evaluate with Gemini
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ==================================================
            4. POLICY: Approved / Blocked
            ================================================== */}
        <div className="py-4 border-b border-[#1b263b] space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-amber-400" />
              <span className="text-[11px] font-mono tracking-wider uppercase text-zinc-400 font-medium">
                Policy Governance (Guarded Autopilot)
              </span>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">
              Deterministic Rules Authorize
            </span>
          </div>

          <div
            className={`p-3.5 rounded-xl border ${
              isApproved
                ? "bg-teal-950/10 border-teal-500/30"
                : "bg-rose-950/10 border-rose-500/30"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-300 font-medium">
                Policy Verdict
              </span>
              {isApproved ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-teal-500/20 text-teal-400 border border-teal-500/40">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  APPROVED
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  BLOCKED
                </span>
              )}
            </div>

            <p className="text-xs text-zinc-300 mt-2 leading-relaxed font-mono">
              {isApproved
                ? (opportunity.policyReason ||
                  "Approved by policy: failure category permits bounded recovery within retry limits.")
                : (opportunity.policyReason ||
                  (isHardDecline
                    ? "Blocked: Hard decline / fraud category violates Autopilot policy."
                    : "Blocked: Permitted retry attempt ceiling (3/3) exceeded."))}
            </p>

            <div className="text-[10px] text-zinc-500 mt-2 font-mono flex items-center justify-between">
              <span>Rule source: Guarded Autopilot</span>
              <span className="text-zinc-400">Strictly Enforced</span>
            </div>
          </div>
        </div>

        {/* ==================================================
            5. LIFECYCLE: Last action / Next eligible action
            ================================================== */}
        <div className="py-4 border-b border-[#1b263b] space-y-2.5">
          <span className="text-[11px] font-mono tracking-wider uppercase text-zinc-400 font-medium block">
            Action Lifecycle
          </span>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-2.5 rounded-lg bg-[#070b16] border border-[#1b263b]">
              <span className="text-[10px] font-mono uppercase text-zinc-500 block">
                Last Action
              </span>
              <span className="font-mono text-zinc-300 mt-0.5 block truncate">
                Payment failed ({opportunity.failureCategory.replace(/_/g, " ")})
              </span>
            </div>

            <div className="p-2.5 rounded-lg bg-[#070b16] border border-[#1b263b]">
              <span className="text-[10px] font-mono uppercase text-zinc-500 block">
                Next Eligible Action
              </span>
              <span className="font-mono text-zinc-300 mt-0.5 block truncate">
                {isBlocked
                  ? "None (Policy Blocked)"
                  : effectiveAiAction === "PAYMENT_LINK"
                  ? "Send Razorpay Test Link"
                  : effectiveAiAction === "RETRY"
                  ? "Simulated Retry Attempt"
                  : "Customer Notification"}
              </span>
            </div>
          </div>
        </div>

        {/* ==================================================
            6. OPERATOR ACTIONS: Inspect Decision, Authorize, Checkout
            ================================================== */}
        <div className="pt-4 space-y-2.5 mt-auto">
          {/* Inspect Decision in Ledger */}
          {onInspectDecision && (
            <button
              onClick={() => onInspectDecision(opportunity.paymentId)}
              className="w-full py-2.5 px-4 rounded-xl bg-[#070b16] hover:bg-[#0d1527] text-zinc-200 border border-[#1b263b] hover:border-blue-500/50 font-medium text-xs transition-all flex items-center justify-center gap-2 font-mono group"
            >
              <span>Inspect Decision in Ledger</span>
              <ExternalLink className="w-3.5 h-3.5 text-blue-400 group-hover:translate-x-0.5 transition-transform" />
            </button>
          )}

          {/* Authorize & Execute Button */}
          <button
            onClick={handleExecute}
            disabled={
              executing ||
              isBlocked ||
              opportunity.status === "captured" ||
              opportunity.recoveryStatus === "recovered"
            }
            className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-sm font-mono"
          >
            {executing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Authorizing & Executing...</span>
              </>
            ) : (
              <>
                <span>Authorize & Execute Recovery</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>

          {/* Razorpay Standard Modal Trigger */}
          <button
            onClick={handleRazorpayModalCheckout}
            disabled={
              checkingOut ||
              opportunity.status === "captured" ||
              opportunity.recoveryStatus === "recovered"
            }
            className="w-full py-2 px-4 rounded-xl bg-zinc-800/70 hover:bg-zinc-800 text-zinc-300 border border-zinc-700/80 font-medium text-xs transition-colors disabled:opacity-50 flex items-center justify-center gap-2 font-mono"
          >
            {checkingOut ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />
                <span>Launching Razorpay Modal...</span>
              </>
            ) : (
              <>
                <CreditCard className="w-3.5 h-3.5 text-amber-400" />
                <span>
                  Simulate Live Recovery Checkout (
                  {formatPaiseToRupees(opportunity.amountPaise)})
                </span>
              </>
            )}
          </button>

          {/* Checkout Feedback Message */}
          {checkoutMsg && (
            <div
              className={`p-2.5 rounded-lg border text-xs font-mono ${
                checkoutMsg.type === "success"
                  ? "bg-teal-950/40 border-teal-500/30 text-teal-300"
                  : "bg-rose-950/40 border-rose-500/30 text-rose-300"
              }`}
            >
              {checkoutMsg.text}
            </div>
          )}

          {/* Execution Result Feedback */}
          {executionResult && (
            <div className="p-3 rounded-lg bg-[#070b16] border border-[#1b263b] text-xs">
              {executionResult.status === "APPROVED" ||
              executionResult.status === "EXECUTED" ? (
                <div className="flex items-center gap-1.5 text-teal-400 font-medium font-mono">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>Action authorized & executed safely via Autopilot.</span>
                </div>
              ) : executionResult.status === "BLOCKED" ? (
                <div className="flex items-center gap-1.5 text-rose-400 font-medium font-mono">
                  <ShieldAlert className="w-4 h-4 shrink-0" />
                  <span>
                    {executionResult.verdict?.blockingReason ||
                      "Action blocked by policy rules."}
                  </span>
                </div>
              ) : (
                <div className="text-zinc-400 font-mono">
                  Status: {executionResult.status}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
