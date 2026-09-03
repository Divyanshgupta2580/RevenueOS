"use client";

import { ChevronRight, Radio, Search } from "lucide-react";
import { useState } from "react";
import type { Opportunity } from "@/lib/types";
import { formatPaiseToRupees } from "@/lib/format";

interface RadarTableProps {
  opportunities: Opportunity[];
  loading: boolean;
  onSelectOpportunity: (opp: Opportunity) => void;
  onRefresh: () => void;
}

export default function RadarTable({
  opportunities,
  loading,
  onSelectOpportunity,
  onRefresh,
}: RadarTableProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const filtered = opportunities.filter((o) =>
    o.paymentId.toLowerCase().includes(searchTerm.toLowerCase()) ||
    o.failureCategory.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="bg-[#0e1117] border border-[#21262d] rounded-lg overflow-hidden my-6">
      {/* Table Toolbar */}
      <div className="px-5 py-4 border-b border-[#21262d] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
            <Radio className="w-4 h-4 text-amber-400" />
            Revenue Radar Opportunities
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Ranked deterministically by Expected Recovery Value (ERV) in integer minor units.
          </p>
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          {/* Search */}
          <div className="relative flex-1 sm:w-64">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by Payment ID..."
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-zinc-900 border border-zinc-700 rounded-md text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-amber-500"
            />
          </div>

          <button
            onClick={onRefresh}
            className="px-3 py-1.5 text-xs font-medium bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 rounded-md transition-colors whitespace-nowrap"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading ? (
        <div className="py-16 text-center text-zinc-400 text-sm">
          <div className="inline-block w-6 h-6 border-2 border-amber-400 border-t-transparent rounded-full animate-spin mb-2" />
          <div>Synchronizing opportunities over WebSocket stream...</div>
        </div>
      ) : filtered.length === 0 ? (
        /* Truthful Empty State (Absolute No-Dummy-Data Requirement) */
        <div className="py-20 px-6 text-center">
          <div className="w-12 h-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-500">
            <Radio className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">No revenue at risk detected</h3>
          <p className="text-xs text-zinc-500 max-w-md mx-auto mt-1.5 leading-relaxed">
            No active payment failures in the queue. RevenueOS is listening to the live Razorpay
            webhook stream and will prioritize failed transactions automatically.
          </p>
        </div>
      ) : (
        /* Table of Opportunities */
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#21262d] bg-zinc-900/50 text-zinc-400 uppercase font-mono text-[10px] tracking-wider">
                <th className="py-3 px-4 font-medium">Payment ID</th>
                <th className="py-3 px-4 font-medium">Amount</th>
                <th className="py-3 px-4 font-medium">Category</th>
                <th className="py-3 px-4 font-medium">Retries</th>
                <th className="py-3 px-4 font-medium">Score</th>
                <th className="py-3 px-4 font-medium text-amber-400">ERV</th>
                <th className="py-3 px-4 font-medium">Priority</th>
                <th className="py-3 px-4 font-medium">Status</th>
                <th className="py-3 px-4 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#21262d]">
              {filtered.map((opp) => (
                <tr
                  key={opp.paymentId}
                  onClick={() => onSelectOpportunity(opp)}
                  className="hover:bg-zinc-800/40 cursor-pointer transition-colors group"
                >
                  <td className="py-3 px-4 font-mono text-zinc-300 font-medium">
                    {opp.paymentId}
                  </td>
                  <td className="py-3 px-4 font-mono text-white font-semibold">
                    {formatPaiseToRupees(opp.amountPaise)}
                  </td>
                  <td className="py-3 px-4 capitalize text-zinc-400">
                    {opp.failureCategory.replace(/_/g, " ")}
                  </td>
                  <td className="py-3 px-4 font-mono text-zinc-400">
                    {opp.retryCount}/{opp.maxRetries}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-12 bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-amber-400 h-full rounded-full"
                          style={{ width: `${Math.min(100, Math.max(0, opp.recoverabilityScore))}%` }}
                        />
                      </div>
                      <span className="font-mono text-[11px] text-zinc-300">
                        {Math.round(opp.recoverabilityScore)}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 font-mono font-semibold text-amber-400">
                    {formatPaiseToRupees(opp.expectedRecoveryValuePaise)}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase border ${
                        opp.priority === "HIGH"
                          ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                          : opp.priority === "MEDIUM"
                          ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                          : "bg-zinc-800 text-zinc-400 border-zinc-700"
                      }`}
                    >
                      {opp.priority}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="capitalize text-zinc-300 font-mono text-[11px]">
                      {opp.recoveryStatus.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectOpportunity(opp);
                      }}
                      className="inline-flex items-center gap-1 text-xs font-medium text-amber-400 group-hover:text-amber-300 transition-colors"
                    >
                      Inspect
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
