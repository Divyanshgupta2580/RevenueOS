"use client";

import { AlertTriangle, TrendingUp, CheckCircle2, BarChart2, Percent } from "lucide-react";
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

  const sampleCount = metrics?.observedSampleSize ?? (recovered > 0 ? 1 : 0);
  const isTinySample = sampleCount < 30;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 my-6">
      {/* 1. Revenue At Risk */}
      <div className="p-4 rounded-xl bg-gradient-to-b from-[#140b14]/80 to-[#091021] border border-rose-500/25 hover:border-rose-500/40 transition-colors relative overflow-hidden shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-500 shrink-0">
                <AlertTriangle className="w-4 h-4" />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-medium">
                REVENUE AT RISK
              </span>
            </div>
            <div className="text-rose-500/70 shrink-0">
              <BarChart2 className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold tracking-tight text-white font-mono">
            {loading ? "..." : formatPaiseToRupees(atRisk)}
          </div>
          <div className="text-xs text-zinc-400 mt-1">Identified failed payments</div>
        </div>
        <div className="text-[10px] text-zinc-500 mt-3 pt-2 border-t border-[#141d30] flex items-center justify-between font-mono">
          <span>Source: MongoDB Atlas</span>
          <span className="text-zinc-400">Integer minor units</span>
        </div>
      </div>

      {/* 2. Expected Recoverable */}
      <div className="p-4 rounded-xl bg-gradient-to-b from-[#141209]/80 to-[#091021] border border-amber-500/25 hover:border-amber-500/40 transition-colors relative overflow-hidden shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500 shrink-0">
                <BarChart2 className="w-4 h-4" />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-medium">
                EXPECTED RECOVERABLE
              </span>
            </div>
            <div className="text-amber-500/70 shrink-0">
              <TrendingUp className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold tracking-tight text-amber-400 font-mono">
            {loading ? "..." : formatPaiseToRupees(expected)}
          </div>
          <div className="text-xs text-zinc-400 mt-1">Deterministic ERV sum</div>
        </div>
        <div className="text-[10px] text-zinc-500 mt-3 pt-2 border-t border-[#141d30] flex items-center justify-between font-mono">
          <span>Model: Radar scoring</span>
          <span className="text-amber-400/80">Authoritative math</span>
        </div>
      </div>

      {/* 3. Actually Recovered */}
      <div className="p-4 rounded-xl bg-gradient-to-b from-[#081514]/80 to-[#091021] border border-teal-500/25 hover:border-teal-500/40 transition-colors relative overflow-hidden shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 shrink-0">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-medium">
                ACTUALLY RECOVERED
              </span>
            </div>
            <div className="text-teal-500/70 shrink-0">
              <TrendingUp className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold tracking-tight text-teal-400 font-mono">
            {loading ? "..." : formatPaiseToRupees(recovered)}
          </div>
          <div className="text-xs text-zinc-400 mt-1">
            {sampleCount > 0 ? `${sampleCount} verified transaction${sampleCount === 1 ? "" : "s"}` : "0 transactions"}
          </div>
        </div>
        <div className="text-[10px] text-zinc-400 mt-3 pt-2 border-t border-[#141d30] flex flex-col gap-0.5 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Attribution:</span>
            <span className={isTinySample ? "text-amber-400/90 font-medium" : "text-teal-400"}>
              {isTinySample ? "Insufficient sample" : "Measured"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Baseline:</span>
            <span className="text-zinc-400">Illustrative</span>
          </div>
        </div>
      </div>

      {/* 4. Estimated Lift */}
      <div className="p-4 rounded-xl bg-gradient-to-b from-[#0a1222]/80 to-[#091021] border border-blue-500/25 hover:border-blue-500/40 transition-colors relative overflow-hidden shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 shrink-0">
                <TrendingUp className="w-4 h-4" />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-medium">
                ESTIMATED LIFT
              </span>
            </div>
            <div className="text-blue-500/70 shrink-0">
              <BarChart2 className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold tracking-tight text-cyan-400 font-mono">
            {loading ? "..." : formatPaiseToRupees(incremental)}
          </div>
          <div className="text-xs text-zinc-400 mt-1">Above baseline control</div>
        </div>
        <div className="text-[10px] text-zinc-400 mt-3 pt-2 border-t border-[#141d30] flex flex-col gap-0.5 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Significance:</span>
            <span className={isTinySample ? "text-amber-400/90 font-medium" : "text-cyan-400"}>
              {isTinySample ? "Insufficient sample" : "Statistically valid"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Baseline:</span>
            <span className="text-zinc-400">8% heuristic</span>
          </div>
        </div>
      </div>

      {/* 5. Recovery Rate */}
      <div className="p-4 rounded-xl bg-gradient-to-b from-[#120a1f]/80 to-[#091021] border border-purple-500/25 hover:border-purple-500/40 transition-colors relative overflow-hidden shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shrink-0">
                <Percent className="w-4 h-4" />
              </div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-medium">
                RECOVERY RATE
              </span>
            </div>
            <div className="text-purple-500/70 shrink-0">
              <TrendingUp className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="text-2xl font-bold tracking-tight text-white font-mono">
            {loading ? "..." : formatPercentage(rate)}
          </div>
          <div className="text-xs text-zinc-400 mt-1">
            {sampleCount > 0 ? `Observed recovery (${sampleCount} txn)` : "Total conversion efficiency"}
          </div>
        </div>
        <div className="text-[10px] text-zinc-400 mt-3 pt-2 border-t border-[#141d30] flex flex-col gap-0.5 font-mono">
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Sample size:</span>
            <span className={isTinySample ? "text-amber-400/90 font-medium" : "text-emerald-400"}>
              {isTinySample ? `${sampleCount} (Low statistical power)` : `${sampleCount} txns`}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Causal claim:</span>
            <span className="text-zinc-400">Non-definitive</span>
          </div>
        </div>
      </div>
    </div>
  );
}
