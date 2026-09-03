"use client";

import { Activity, CheckCircle, ShieldAlert, FileText } from "lucide-react";
import type { DecisionRecord } from "@/lib/types";
import { formatIsoDate } from "@/lib/format";

interface DecisionLedgerProps {
  decisions: DecisionRecord[];
  loading: boolean;
}

export default function DecisionLedger({ decisions, loading }: DecisionLedgerProps) {
  return (
    <div className="bg-[#0e1117] border border-[#21262d] rounded-lg overflow-hidden my-6">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[#21262d] flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            Decision Ledger & Audit Timeline
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
                <th className="py-3 px-4 font-medium">Policy Result</th>
                <th className="py-3 px-4 font-medium">Reason / Rule</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#21262d]">
              {decisions.map((d) => {
                const isApproved = d.policyDecision?.status === "APPROVED";
                return (
                  <tr key={d.decisionId} className="hover:bg-zinc-800/30 transition-colors">
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
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30">
                        {d.aiRecommendation?.action || "RETRY"}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-300">
                      {d.aiRecommendation?.confidence
                        ? `${(d.aiRecommendation.confidence * 100).toFixed(0)}%`
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
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
