"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpDown,
  CheckCircle2,
  ChevronRight,
  Clock,
  Info,
  Radio,
  RotateCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
  CreditCard,
} from "lucide-react";
import type { Opportunity } from "@/lib/types";
import { formatPaiseToRupees } from "@/lib/format";

interface RadarTableProps {
  opportunities: Opportunity[];
  loading: boolean;
  onSelectOpportunity: (opp: Opportunity) => void;
  onRefresh: () => void;
  onGoToCheckout?: () => void;
}

type SortField = "erv" | "score" | "amount" | "age";

export default function RadarTable({
  opportunities,
  loading,
  onSelectOpportunity,
  onRefresh,
  onGoToCheckout,
}: RadarTableProps) {
  // Operational filters
  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [riskFilter, setRiskFilter] = useState("ALL");
  const [actionFilter, setActionFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState<SortField>("erv");

  // Executive summary aggregations (Strictly 100% real backend data)
  const totalRevenueAtRiskPaise = useMemo(() => {
    return opportunities.reduce((sum, o) => sum + (o.amountPaise || 0), 0);
  }, [opportunities]);

  const totalExpectedRecoverablePaise = useMemo(() => {
    return opportunities.reduce(
      (sum, o) => sum + (o.expectedRecoveryValuePaise || 0),
      0
    );
  }, [opportunities]);

  const atRiskCount = opportunities.length;

  const averageRecoverability = useMemo(() => {
    if (opportunities.length === 0) return 0;
    const totalScore = opportunities.reduce(
      (sum, o) => sum + (o.recoverabilityScore || 0),
      0
    );
    return Math.round(totalScore / opportunities.length);
  }, [opportunities]);

  // Filter and sort opportunities deterministically
  const filteredOpportunities = useMemo(() => {
    const list = opportunities.filter((opp) => {
      // 1. Search term (payment ID, customer, order ID, failure reason)
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase().trim();
        const matchesId = opp.paymentId.toLowerCase().includes(term);
        const matchesCustomer = (opp.customerMasked || "")
          .toLowerCase()
          .includes(term);
        const matchesOrder = (opp.orderId || "").toLowerCase().includes(term);
        const matchesReason = (opp.failureReason || "")
          .toLowerCase()
          .includes(term);
        if (!matchesId && !matchesCustomer && !matchesOrder && !matchesReason) {
          return false;
        }
      }

      // 2. Failure category filter
      if (categoryFilter !== "ALL") {
        if (
          opp.failureCategory.toLowerCase() !== categoryFilter.toLowerCase()
        ) {
          return false;
        }
      }

      // 3. Recovery state filter
      if (statusFilter !== "ALL") {
        if (opp.recoveryStatus.toLowerCase() !== statusFilter.toLowerCase()) {
          return false;
        }
      }

      // 4. Risk level filter
      if (riskFilter !== "ALL") {
        if (riskFilter === "HIGH" && opp.recoverabilityScore < 70) return false;
        if (
          riskFilter === "MEDIUM" &&
          (opp.recoverabilityScore < 40 || opp.recoverabilityScore >= 70)
        )
          return false;
        if (riskFilter === "LOW" && opp.recoverabilityScore >= 40) return false;
      }

      // 5. Recommended action filter
      if (actionFilter !== "ALL") {
        const oppAction =
          opp.recommendedIntervention ||
          opp.heuristicRecommendedAction ||
          "STOP";
        if (oppAction.toUpperCase() !== actionFilter.toUpperCase()) {
          return false;
        }
      }

      return true;
    });

    // Deterministic sorting
    return list.sort((a, b) => {
      if (sortBy === "erv") {
        if (b.expectedRecoveryValuePaise !== a.expectedRecoveryValuePaise) {
          return b.expectedRecoveryValuePaise - a.expectedRecoveryValuePaise;
        }
        return b.recoverabilityScore - a.recoverabilityScore;
      }
      if (sortBy === "score") {
        if (b.recoverabilityScore !== a.recoverabilityScore) {
          return b.recoverabilityScore - a.recoverabilityScore;
        }
        return b.expectedRecoveryValuePaise - a.expectedRecoveryValuePaise;
      }
      if (sortBy === "amount") {
        return b.amountPaise - a.amountPaise;
      }
      if (sortBy === "age") {
        return (
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      }
      return 0;
    });
  }, [
    opportunities,
    searchTerm,
    categoryFilter,
    statusFilter,
    riskFilter,
    actionFilter,
    sortBy,
  ]);

  const hasActiveFilters =
    searchTerm.trim() !== "" ||
    categoryFilter !== "ALL" ||
    statusFilter !== "ALL" ||
    riskFilter !== "ALL" ||
    actionFilter !== "ALL";

  const clearFilters = () => {
    setSearchTerm("");
    setCategoryFilter("ALL");
    setStatusFilter("ALL");
    setRiskFilter("ALL");
    setActionFilter("ALL");
    setSortBy("erv");
  };

  // Semantic styling helper for failure categories
  const getCategoryBadge = (category: string) => {
    const cat = category.toLowerCase();
    if (cat.includes("fraud") || cat.includes("stolen")) {
      return "bg-rose-500/10 text-rose-400 border-rose-500/30";
    }
    if (cat.includes("hard_decline") || cat.includes("expired")) {
      return "bg-rose-500/10 text-rose-400 border-rose-500/30";
    }
    if (cat.includes("soft_decline")) {
      return "bg-indigo-500/10 text-indigo-400 border-indigo-500/30";
    }
    if (cat.includes("insufficient")) {
      return "bg-amber-500/10 text-amber-400 border-amber-500/30";
    }
    if (cat.includes("timeout") || cat.includes("network")) {
      return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
    }
    return "bg-zinc-800 text-zinc-300 border-zinc-700";
  };

  // State badge styling
  const getStateBadge = (state: string) => {
    const s = state.toLowerCase();
    if (s.includes("recovered")) {
      return "bg-teal-500/10 text-teal-400 border-teal-500/30";
    }
    if (s.includes("link_sent") || s.includes("ready")) {
      return "bg-blue-500/10 text-blue-400 border-blue-500/30";
    }
    if (s.includes("retrying")) {
      return "bg-amber-500/10 text-amber-400 border-amber-500/30";
    }
    if (s.includes("blocked") || s.includes("abandoned")) {
      return "bg-rose-500/10 text-rose-400 border-rose-500/30";
    }
    return "bg-zinc-800/80 text-zinc-300 border-zinc-700";
  };

  return (
    <div className="space-y-6 my-6 animate-in fade-in duration-200">
      {/* ==================================================
          PAGE HERO
          ================================================== */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[#1b263b] pb-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono tracking-widest uppercase font-semibold text-blue-400 bg-blue-500/10 px-2.5 py-0.5 rounded border border-blue-500/20">
              REVENUE RADAR
            </span>
            <span className="text-zinc-500 text-xs">&bull;</span>
            <span className="text-xs text-zinc-400 font-mono">
              Live Decision Console
            </span>
            <span className="text-zinc-500 text-xs">&bull;</span>
            <span className="text-xs text-zinc-400 font-mono">
              Revenue Radar Opportunities
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mt-2">
            Revenue at Risk, Before It Becomes Lost Revenue
          </h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1.5 max-w-3xl leading-relaxed">
            RevenueOS continuously identifies failed payments, estimates
            recoverability, and recommends the safest bounded recovery action.
          </p>
        </div>

        {/* Live sync indicator */}
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 self-start md:self-end shrink-0">
          <span className="w-2 h-2 rounded-full bg-teal-400 shadow-[0_0_8px_rgba(20,184,166,0.6)]" />
          <span>MongoDB Atlas Real-Time Feed</span>
        </div>
      </div>

      {/* ==================================================
          EXECUTIVE SUMMARY (Compact 4 Tiles)
          ================================================== */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* Tile 1: Revenue at Risk */}
        <div className="p-4 rounded-xl bg-[#091021] border border-[#1b263b] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono tracking-wider text-zinc-400 font-medium">
              Revenue at Risk
            </span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-white font-mono mt-2">
            {loading ? "..." : formatPaiseToRupees(totalRevenueAtRiskPaise)}
          </div>
          <div className="text-[11px] text-zinc-500 mt-2 font-mono flex items-center justify-between">
            <span>Active failed payments</span>
            <span className="text-rose-400/90 font-medium">Unsettled</span>
          </div>
        </div>

        {/* Tile 2: Expected Recoverable */}
        <div className="p-4 rounded-xl bg-[#091021] border border-[#1b263b] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono tracking-wider text-zinc-400 font-medium">
              Expected Recovery Value
            </span>
            <TrendingUp className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-amber-400 font-mono mt-2">
            {loading ? "..." : formatPaiseToRupees(totalExpectedRecoverablePaise)}
          </div>
          <div className="text-[11px] text-zinc-500 mt-2 font-mono flex items-center justify-between">
            <span>Deterministic ERV sum</span>
            <span className="text-amber-400/90 font-medium">Mathematical</span>
          </div>
        </div>

        {/* Tile 3: At-Risk Payments */}
        <div className="p-4 rounded-xl bg-[#091021] border border-[#1b263b] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-medium">
              AT-RISK PAYMENTS
            </span>
            <Radio className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-white font-mono mt-2">
            {loading ? "..." : atRiskCount}
          </div>
          <div className="text-[11px] text-zinc-500 mt-2 font-mono flex items-center justify-between">
            <span>In recovery queue</span>
            <span className="text-blue-400 font-medium">Ranked #1 to #{atRiskCount || 0}</span>
          </div>
        </div>

        {/* Tile 4: Average Recoverability */}
        <div className="p-4 rounded-xl bg-[#091021] border border-[#1b263b] shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-400 font-medium">
              AVG RECOVERABILITY
            </span>
            <ShieldCheck className="w-4 h-4 text-teal-400" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-teal-400 font-mono mt-2">
            {loading ? "..." : atRiskCount > 0 ? `${averageRecoverability}%` : "—"}
          </div>
          <div className="text-[11px] text-zinc-500 mt-2 font-mono flex items-center justify-between">
            <span>Taxonomy scoring</span>
            <span className="text-teal-400 font-medium">Deterministic</span>
          </div>
        </div>
      </div>

      {/* ==================================================
          CONTROL BAR (Professional Operational Filters)
          ================================================== */}
      <div className="p-3.5 rounded-xl bg-[#091021] border border-[#1b263b] shadow-sm">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by Payment ID, Customer, Reason..."
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-[#070b16] border border-[#1b263b] rounded-lg text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/40 transition-all font-mono"
            />
          </div>

          {/* Filter Dropdowns */}
          <div className="flex flex-wrap items-center gap-2">
            {/* 1. Failure Category */}
            <div className="relative">
              <select
                aria-label="Filter by failure category"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="appearance-none text-xs bg-[#070b16] border border-[#1b263b] text-zinc-300 rounded-lg pl-2.5 pr-7 py-1.5 focus:outline-none focus:border-blue-500 transition-colors font-mono cursor-pointer"
              >
                <option value="ALL">All Categories</option>
                <option value="soft_decline">Soft Decline</option>
                <option value="insufficient_funds">Insufficient Funds</option>
                <option value="network_timeout">Network Timeout</option>
                <option value="gateway_error">Gateway Error</option>
                <option value="hard_decline">Hard Decline</option>
                <option value="fraud">Fraud</option>
              </select>
            </div>

            {/* 2. Recovery State */}
            <div className="relative">
              <select
                aria-label="Filter by recovery state"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="appearance-none text-xs bg-[#070b16] border border-[#1b263b] text-zinc-300 rounded-lg pl-2.5 pr-7 py-1.5 focus:outline-none focus:border-blue-500 transition-colors font-mono cursor-pointer"
              >
                <option value="ALL">All States</option>
                <option value="pending">At Risk</option>
                <option value="link_sent">Link Sent</option>
                <option value="retrying">Retrying</option>
                <option value="reminded">Reminded</option>
                <option value="stopped">Stopped</option>
                <option value="recovered">Recovered</option>
              </select>
            </div>

            {/* 3. Risk Level */}
            <div className="relative">
              <select
                aria-label="Filter by risk level"
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
                className="appearance-none text-xs bg-[#070b16] border border-[#1b263b] text-zinc-300 rounded-lg pl-2.5 pr-7 py-1.5 focus:outline-none focus:border-blue-500 transition-colors font-mono cursor-pointer"
              >
                <option value="ALL">All Risk Levels</option>
                <option value="HIGH">High Score (70+)</option>
                <option value="MEDIUM">Medium Score (40–69)</option>
                <option value="LOW">Low Score (&lt;40)</option>
              </select>
            </div>

            {/* 4. Recommended Action */}
            <div className="relative">
              <select
                aria-label="Filter by recommended action"
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="appearance-none text-xs bg-[#070b16] border border-[#1b263b] text-zinc-300 rounded-lg pl-2.5 pr-7 py-1.5 focus:outline-none focus:border-blue-500 transition-colors font-mono cursor-pointer"
              >
                <option value="ALL">All AI Actions</option>
                <option value="PAYMENT_LINK">Payment Link</option>
                <option value="RETRY">Simulated Retry</option>
                <option value="REMINDER">Reminder</option>
                <option value="STOP">Stop</option>
              </select>
            </div>

            {/* 5. Sort By */}
            <div className="relative flex items-center">
              <ArrowUpDown className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 pointer-events-none" />
              <select
                aria-label="Sort opportunities by"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortField)}
                className="appearance-none text-xs bg-[#070b16] border border-[#1b263b] text-zinc-300 rounded-lg pl-7 pr-7 py-1.5 focus:outline-none focus:border-blue-500 transition-colors font-mono cursor-pointer"
              >
                <option value="erv">Sort: Expected Recovery (ERV)</option>
                <option value="score">Sort: Recoverability Score</option>
                <option value="amount">Sort: Amount (High to Low)</option>
                <option value="age">Sort: Age (Newest First)</option>
              </select>
            </div>

            {/* Reset Filters */}
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs text-zinc-400 hover:text-white bg-zinc-800/80 hover:bg-zinc-800 border border-zinc-700 rounded-lg transition-colors font-mono"
              >
                <X className="w-3 h-3" />
                Clear
              </button>
            )}

            {/* Refresh Button */}
            <button
              onClick={onRefresh}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg shadow-sm transition-colors disabled:opacity-50 ml-auto whitespace-nowrap"
            >
              <RotateCw
                className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* ==================================================
          PRIMARY OPPORTUNITY TABLE & RESPONSIVE LIST
          ================================================== */}
      {loading ? (
        <div className="py-20 text-center rounded-xl bg-[#091021] border border-[#1b263b]">
          <div className="inline-block w-7 h-7 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-3" />
          <div className="text-sm font-medium text-zinc-200">
            Scanning Revenue at Risk Opportunities...
          </div>
          <p className="text-xs text-zinc-500 mt-1 font-mono">
            Ingesting live MongoDB payments and computing deterministic ERVs
          </p>
        </div>
      ) : filteredOpportunities.length === 0 ? (
        /* ==================================================
            TRUTHFUL EMPTY STATE (Zero Fake Opportunities)
            ================================================== */
        <div className="py-16 px-6 text-center rounded-xl bg-[#091021] border border-[#1b263b]">
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mx-auto mb-3 text-blue-400">
            <Radio className="w-6 h-6" />
          </div>
          <h2 className="text-base font-bold text-white">
            {hasActiveFilters
              ? "No matching opportunities for current filters"
              : "No revenue is currently at risk"}
          </h2>
          <p className="text-xs text-zinc-400 max-w-lg mx-auto mt-2 leading-relaxed">
            {hasActiveFilters
              ? "Try adjusting your filter settings or search terms to inspect more payment records."
              : "No revenue at risk detected. RevenueOS is listening for real payment failures and webhook events. Once a payment fails, it will appear here ranked by Expected Recovery Value."}
          </p>

          {!hasActiveFilters && onGoToCheckout && (
            <div className="mt-5 p-4 max-w-md mx-auto rounded-lg bg-[#070b16] border border-[#1b263b] text-left">
              <div className="flex items-start gap-2.5">
                <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs text-zinc-300">
                  <span className="font-semibold text-white">
                    Need test data to demonstrate Revenue Radar?
                  </span>
                  <p className="text-zinc-400 text-[11px] mt-1 leading-relaxed">
                    Open the Checkout tab to simulate a real payment transaction
                    using Razorpay Test Mode credentials.
                  </p>
                  <button
                    onClick={onGoToCheckout}
                    className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition-colors"
                  >
                    <CreditCard className="w-3.5 h-3.5" />
                    Simulate Test Transaction
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <>
          {/* DESKTOP TABLE VIEW (Visible on lg screens >= 1024px) */}
          <div className="hidden lg:block rounded-xl bg-[#091021] border border-[#1b263b] overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[#1b263b] bg-[#0c1429] text-zinc-400 uppercase font-mono text-[10px] tracking-wider">
                    <th className="py-3 px-2.5 font-medium">Priority</th>
                    <th className="py-3 px-2.5 font-medium">Payment</th>
                    <th className="py-3 px-2.5 font-medium">Customer</th>
                    <th className="py-3 px-2.5 font-medium">Amount</th>
                    <th className="py-3 px-2.5 font-medium">Failure</th>
                    <th className="py-3 px-2.5 font-medium">Age</th>
                    <th className="py-3 px-2.5 font-medium">Recoverability</th>
                    <th className="py-3 px-2.5 font-medium">Expected Recovery</th>
                    <th className="py-3 px-2.5 font-medium">AI Recommendation</th>
                    <th className="py-3 px-2.5 font-medium">Policy</th>
                    <th className="py-3 px-2.5 font-medium">State</th>
                    <th className="py-3 px-2.5 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#162035]">
                  {filteredOpportunities.map((opp, idx) => {
                    const score = Math.round(opp.recoverabilityScore);
                    const aiAction =
                      opp.recommendedIntervention ||
                      opp.heuristicRecommendedAction ||
                      "STOP";
                    const isApproved =
                      opp.policyStatus === "APPROVED" ||
                      (!opp.policyStatus &&
                        opp.nextEligibleAction !== "STOP" &&
                        score >= 20);

                    return (
                      <tr
                        key={opp.paymentId}
                        onClick={() => onSelectOpportunity(opp)}
                        className="hover:bg-[#0f1930] cursor-pointer transition-colors group"
                      >
                        {/* 1. Priority */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-[10px] font-semibold text-zinc-400">
                              #{idx + 1}
                            </span>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold uppercase ${
                                opp.priority === "HIGH"
                                  ? "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                                  : opp.priority === "MEDIUM"
                                  ? "bg-blue-500/10 text-blue-400 border border-blue-500/30"
                                  : "bg-zinc-800 text-zinc-400 border border-zinc-700"
                              }`}
                            >
                              {opp.priority}
                            </span>
                          </div>
                        </td>

                        {/* 2. Payment */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          <div className="font-mono text-white font-medium text-xs">
                            {opp.paymentId}
                          </div>
                          {opp.orderId && (
                            <div className="font-mono text-[10px] text-zinc-500 mt-0.5">
                              {opp.orderId}
                            </div>
                          )}
                        </td>

                        {/* 3. Customer */}
                        <td className="py-3 px-2.5 whitespace-nowrap font-mono text-zinc-400 text-[11px]">
                          {opp.customerMasked || "Anonymous"}
                        </td>

                        {/* 4. Amount */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          <span className="font-mono text-white font-bold text-sm">
                            {formatPaiseToRupees(opp.amountPaise)}
                          </span>
                        </td>

                        {/* 5. Failure */}
                        <td className="py-3 px-2.5 max-w-[170px]">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-mono font-medium border capitalize whitespace-nowrap ${getCategoryBadge(
                              opp.failureCategory
                            )}`}
                          >
                            {opp.failureCategory.replace(/_/g, " ")}
                          </span>
                          <div
                            className="text-[11px] text-zinc-400 truncate mt-0.5"
                            title={opp.failureReason}
                          >
                            {opp.failureReason}
                          </div>
                        </td>

                        {/* 6. Age */}
                        <td className="py-3 px-2.5 whitespace-nowrap font-mono text-[11px] text-zinc-400">
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-zinc-400" />
                            <span>{opp.paymentAge || "Just now"}</span>
                          </div>
                          <div className="text-[10px] text-zinc-400 mt-0.5">
                            {opp.retryCount}/{opp.maxRetries} retries
                          </div>
                        </td>

                        {/* 7. Recoverability */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <div className="w-14 bg-[#070b16] rounded-full h-1.5 overflow-hidden border border-zinc-800">
                              <div
                                className={`h-full rounded-full ${
                                  score >= 70
                                    ? "bg-teal-400"
                                    : score >= 40
                                    ? "bg-amber-400"
                                    : "bg-rose-500"
                                }`}
                                style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                              />
                            </div>
                            <span className="font-mono text-xs font-semibold text-white">
                              {score}
                              <span className="text-zinc-500 text-[10px] font-normal">
                                /100
                              </span>
                            </span>
                          </div>
                          <span className="text-[9px] font-mono text-zinc-500 uppercase">
                            Deterministic score
                          </span>
                        </td>

                        {/* 8. Expected Recovery */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          <div className="font-mono font-bold text-amber-400 text-sm">
                            {formatPaiseToRupees(opp.expectedRecoveryValuePaise)}
                          </div>
                          <span className="text-[9px] font-mono text-zinc-500 uppercase">
                            Backend calculated
                          </span>
                        </td>

                        {/* 9. AI Recommendation */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30">
                              <Sparkles className="w-3 h-3 text-blue-400" />
                              {aiAction.replace(/_/g, " ")}
                            </span>
                            {typeof opp.aiConfidence === "number" && (
                              <span className="text-[10px] font-mono text-zinc-400 font-medium">
                                {Math.round(opp.aiConfidence * 100)}%
                              </span>
                            )}
                          </div>
                          <div className="text-[9px] font-mono text-zinc-500 mt-0.5">
                            AI recommendation
                          </div>
                        </td>

                        {/* 10. Policy */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          {isApproved ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/30">
                              <CheckCircle2 className="w-3 h-3" />
                              APPROVED
                            </span>
                          ) : (
                            <span
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30"
                              title={opp.policyReason || "Action blocked by policy rules"}
                            >
                              <ShieldAlert className="w-3 h-3" />
                              BLOCKED
                            </span>
                          )}
                        </td>

                        {/* 11. State */}
                        <td className="py-3 px-2.5 whitespace-nowrap">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium border uppercase ${getStateBadge(
                              opp.recoveryStatus
                            )}`}
                          >
                            {opp.recoveryStatus.replace(/_/g, " ")}
                          </span>
                        </td>

                        {/* 12. Primary Action */}
                        <td className="py-3 px-2.5 text-right whitespace-nowrap">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectOpportunity(opp);
                            }}
                            className="inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold bg-blue-600/10 hover:bg-blue-600 text-blue-400 hover:text-white border border-blue-500/30 hover:border-blue-500 rounded-md transition-all shadow-sm"
                          >
                            <span>Inspect</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* MOBILE & TABLET RESPONSIVE CARD VIEW (Visible on screens < 1024px) */}
          <div className="lg:hidden space-y-3">
            {filteredOpportunities.map((opp, idx) => {
              const score = Math.round(opp.recoverabilityScore);
              const aiAction =
                opp.recommendedIntervention ||
                opp.heuristicRecommendedAction ||
                "STOP";
              const isApproved =
                opp.policyStatus === "APPROVED" ||
                (!opp.policyStatus &&
                  opp.nextEligibleAction !== "STOP" &&
                  score >= 20);

              return (
                <div
                  key={opp.paymentId}
                  onClick={() => onSelectOpportunity(opp)}
                  className="p-4 rounded-xl bg-[#091021] border border-[#1b263b] shadow-sm hover:border-[#273752] transition-colors cursor-pointer space-y-3"
                >
                  {/* Top: Rank, ID, State, Amount */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-zinc-400">
                        #{idx + 1}
                      </span>
                      <div>
                        <div className="font-mono font-semibold text-white text-xs">
                          {opp.paymentId}
                        </div>
                        <div className="font-mono text-[10px] text-zinc-400">
                          {opp.customerMasked || "Anonymous"} &bull;{" "}
                          {opp.paymentAge || "Just now"}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono font-bold text-white text-base">
                        {formatPaiseToRupees(opp.amountPaise)}
                      </div>
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-mono border uppercase mt-0.5 ${getStateBadge(
                          opp.recoveryStatus
                        )}`}
                      >
                        {opp.recoveryStatus.replace(/_/g, " ")}
                      </span>
                    </div>
                  </div>

                  {/* Failure reason tag */}
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono border capitalize ${getCategoryBadge(
                        opp.failureCategory
                      )}`}
                    >
                      {opp.failureCategory.replace(/_/g, " ")}
                    </span>
                    <span className="text-[11px] text-zinc-400 truncate flex-1">
                      {opp.failureReason}
                    </span>
                  </div>

                  {/* Metric Tiles (Recoverability & ERV) */}
                  <div className="grid grid-cols-2 gap-2 p-2.5 rounded-lg bg-[#070b16] border border-[#141d30]">
                    <div>
                      <div className="text-[10px] font-mono text-zinc-400 uppercase">
                        Recoverability
                      </div>
                      <div className="font-mono font-bold text-white text-sm mt-0.5 flex items-center gap-1.5">
                        <span>{score}/100</span>
                        <div className="w-10 bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="bg-teal-400 h-full rounded-full"
                            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                          />
                        </div>
                      </div>
                      <span className="text-[9px] font-mono text-zinc-400">
                        Deterministic score
                      </span>
                    </div>
                    <div>
                      <div className="text-[10px] font-mono text-zinc-400 uppercase">
                        Expected Recovery
                      </div>
                      <div className="font-mono font-bold text-amber-400 text-sm mt-0.5">
                        {formatPaiseToRupees(opp.expectedRecoveryValuePaise)}
                      </div>
                      <span className="text-[9px] font-mono text-zinc-400">
                        Backend calculated
                      </span>
                    </div>
                  </div>

                  {/* Recommendation & Policy Status */}
                  <div className="flex items-center justify-between pt-1 border-t border-[#141d30]">
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase block">
                        AI Recommendation
                      </span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30">
                          <Sparkles className="w-3 h-3 text-blue-400" />
                          {aiAction.replace(/_/g, " ")}
                        </span>
                        {typeof opp.aiConfidence === "number" && (
                          <span className="text-[10px] font-mono text-zinc-400">
                            {Math.round(opp.aiConfidence * 100)}%
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-mono text-zinc-400 uppercase block">
                        Policy Decision
                      </span>
                      <div className="mt-0.5">
                        {isApproved ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-teal-500/10 text-teal-400 border border-teal-500/30">
                            <CheckCircle2 className="w-3 h-3" />
                            APPROVED
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
                            <ShieldAlert className="w-3 h-3" />
                            BLOCKED
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Primary Action Button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectOpportunity(opp);
                    }}
                    className="w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-colors flex items-center justify-center gap-1.5 shadow-sm"
                  >
                    <span>Inspect Opportunity</span>
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
