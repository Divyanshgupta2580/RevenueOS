"use client";

import { TrendingUp, ShieldCheck, Zap, BarChart3, Info } from "lucide-react";
import type { MetricSummary } from "@/lib/types";
import { formatPaiseToRupees, formatPercentage } from "@/lib/format";

interface MetricsViewProps {
  metrics: MetricSummary | null;
}

export default function MetricsView({ metrics }: MetricsViewProps) {
  const atRisk = metrics?.revenueAtRiskPaise ?? 0;
  const actual = metrics?.actuallyRecoveredPaise ?? 0;
  // Baseline assumption: unguided naive retry typically yields ~8% of at-risk revenue
  const baseline = Math.floor(atRisk * 0.08);
  const incremental = Math.max(0, actual - baseline);
  const recoveryRate = metrics?.recoveryRate ?? 0;

  const hasData = atRisk > 0 || actual > 0;

  return (
    <div className="space-y-6 my-6">
      {/* Top Banner */}
      <div className="p-5 rounded-lg bg-[#0e1117] border border-[#21262d]">
        <h2 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-emerald-400" />
          Measured Outcome & Incremental Recovery Lift
        </h2>
        <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
          Comparing baseline unguided recovery outcomes against RevenueOS intelligent decisioning.
          All financial calculations are computed deterministically using integer minor units (paise).
        </p>
      </div>

      {!hasData ? (
        /* Truthful Empty State (Absolute No-Dummy-Data Requirement) */
        <div className="py-20 px-6 text-center bg-[#0e1117] border border-[#21262d] rounded-lg">
          <div className="w-12 h-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center mx-auto mb-3 text-zinc-500">
            <Info className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">Insufficient outcome data</h3>
          <p className="text-xs text-zinc-500 max-w-md mx-auto mt-1.5 leading-relaxed">
            No recovery interventions have reached final webhook capture status yet.
            Outcome metrics will populate with verified Razorpay webhook captures as payments succeed.
          </p>
        </div>
      ) : (
        <>
          {/* Comparative Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Baseline Assumption */}
            <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d]">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                Baseline Assumption (X)
              </span>
              <div className="text-2xl font-bold font-mono text-zinc-400 mt-1">
                {formatPaiseToRupees(baseline)}
              </div>
              <p className="text-[11px] text-zinc-500 mt-1.5 leading-relaxed">
                8% heuristic evaluation model (assumed unguided retry rate; not empirical merchant data).
              </p>
            </div>

            {/* Observed Test-Mode Recovery */}
            <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d] relative overflow-hidden">
              <span className="text-xs font-medium uppercase tracking-wider text-emerald-400">
                Observed Recovery (Y)
              </span>
              <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
                {formatPaiseToRupees(actual)}
              </div>
              <p className="text-[11px] text-zinc-400 mt-1.5 leading-relaxed">
                Test-mode validated recovery via Gemini recommendations and Guarded Autopilot.
              </p>
            </div>

            {/* Incremental Lift */}
            <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d] relative overflow-hidden">
              <span className="text-xs font-medium uppercase tracking-wider text-cyan-400">
                Estimated Lift (Y - X)
              </span>
              <div className="text-2xl font-bold font-mono text-cyan-400 mt-1">
                {formatPaiseToRupees(incremental)}
              </div>
              <p className="text-[11px] text-zinc-400 mt-1.5 leading-relaxed">
                Recovery above the 8% baseline evaluation assumption.
              </p>
            </div>

            {/* Production Merchant Status */}
            <div className="p-4 rounded-lg bg-[#0e1117] border border-amber-500/20 relative overflow-hidden">
              <span className="text-xs font-medium uppercase tracking-wider text-amber-400">
                Production Recovery
              </span>
              <div className="text-lg font-bold font-mono text-amber-400 mt-1">
                Not measured
              </div>
              <p className="text-[11px] text-zinc-500 mt-1.5 leading-relaxed">
                Live production merchant traffic has not been connected in test mode.
              </p>
            </div>
          </div>

          {/* Strategy Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d]">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5 mb-3">
                <TrendingUp className="w-3.5 h-3.5 text-amber-400" />
                Conversion Efficiency
              </h3>
              <div className="space-y-2.5 text-xs">
                <div className="flex justify-between py-1 border-b border-zinc-800">
                  <span className="text-zinc-400">Overall Recovery Rate</span>
                  <span className="font-mono text-white font-medium">{formatPercentage(recoveryRate)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-800">
                  <span className="text-zinc-400">Total At Risk Identified</span>
                  <span className="font-mono text-white font-medium">{formatPaiseToRupees(atRisk)}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-zinc-400">Active Opportunities Tracked</span>
                  <span className="font-mono text-white font-medium">{metrics?.activeOpportunities ?? 0}</span>
                </div>
              </div>
            </div>

            <div className="p-4 rounded-lg bg-[#0e1117] border border-[#21262d]">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5 mb-3">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                Guarded Autopilot Protection
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                The deterministic policy engine prevents wasted gateway fees and customer churn by
                blocking retries on hard declines, stolen cards, and maxed retry thresholds.
              </p>
              <div className="mt-4 p-2.5 bg-zinc-900 rounded border border-zinc-800 text-[11px] text-zinc-300 font-mono">
                <Zap className="w-3.5 h-3.5 text-amber-400 inline mr-1" />
                Policy Engine: 100% auditable rule validation on every action.
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
