"use client";

import { AlertTriangle, TrendingUp, CheckCircle, ShieldCheck, Zap } from "lucide-react";
import type { MetricSummary } from "@/lib/types";
import { formatPaiseToRupees, formatPercentage } from "@/lib/format";

interface MetricsCardsProps {
  metrics: MetricSummary | null;
  loading: boolean;
}

export default function MetricsCards({ metrics, loading }: MetricsCardsProps) {
  const atRisk = metrics?.revenueAtRiskPaise ?? 0;
  const expected = metrics?.expectedRecoverablePaise ?? 0;
  const recovered = metrics?.actuallyRecoveredPaise ?? 0;
  const incremental = metrics?.incrementalRevenuePaise ?? 0;
  const rate = metrics?.recoveryRate ?? 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3.5 my-6">
      {/* Revenue At Risk */}
      <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d] relative overflow-hidden">
        <div className="flex items-center justify-between text-zinc-400 mb-1.5">
          <span className="text-xs font-medium uppercase tracking-wider">Revenue at Risk</span>
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
        </div>
        <div className="text-xl font-semibold tracking-tight text-white font-mono">
          {loading ? "..." : formatPaiseToRupees(atRisk)}
        </div>
        <div className="text-[11px] text-zinc-500 mt-1">Identified failed payments</div>
      </div>

      {/* Expected Recoverable */}
      <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d] relative overflow-hidden">
        <div className="flex items-center justify-between text-zinc-400 mb-1.5">
          <span className="text-xs font-medium uppercase tracking-wider">Expected Recoverable</span>
          <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <div className="text-xl font-semibold tracking-tight text-amber-400 font-mono">
          {loading ? "..." : formatPaiseToRupees(expected)}
        </div>
        <div className="text-[11px] text-zinc-500 mt-1">Deterministic ERV sum</div>
      </div>

      {/* Actually Recovered */}
      <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d] relative overflow-hidden">
        <div className="flex items-center justify-between text-zinc-400 mb-1.5">
          <span className="text-xs font-medium uppercase tracking-wider">Actually Recovered</span>
          <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <div className="text-xl font-semibold tracking-tight text-emerald-400 font-mono">
          {loading ? "..." : formatPaiseToRupees(recovered)}
        </div>
        <div className="text-[11px] text-zinc-500 mt-1">Verified webhook captures</div>
      </div>

      {/* Incremental Revenue */}
      <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d] relative overflow-hidden">
        <div className="flex items-center justify-between text-zinc-400 mb-1.5">
          <span className="text-xs font-medium uppercase tracking-wider">Incremental Lift</span>
          <Zap className="w-3.5 h-3.5 text-cyan-400" />
        </div>
        <div className="text-xl font-semibold tracking-tight text-cyan-400 font-mono">
          {loading ? "..." : formatPaiseToRupees(incremental)}
        </div>
        <div className="text-[11px] text-zinc-500 mt-1">Measured lift (Y - X)</div>
      </div>

      {/* Recovery Rate */}
      <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d] relative overflow-hidden col-span-2 md:col-span-1">
        <div className="flex items-center justify-between text-zinc-400 mb-1.5">
          <span className="text-xs font-medium uppercase tracking-wider">Recovery Rate</span>
          <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
        </div>
        <div className="text-xl font-semibold tracking-tight text-white font-mono">
          {loading ? "..." : formatPercentage(rate)}
        </div>
        <div className="text-[11px] text-zinc-500 mt-1">Total conversion efficiency</div>
      </div>
    </div>
  );
}
