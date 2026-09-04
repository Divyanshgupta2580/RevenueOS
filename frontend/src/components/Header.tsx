"use client";

import { useState } from "react";
import {
  LayoutGrid,
  FileText,
  TrendingUp,
  CreditCard,
  Shield,
  RotateCw,
  LogOut,
} from "lucide-react";
import type { ConnectionState, UserContext } from "@/lib/types";

interface HeaderProps {
  activeTab: "radar" | "ledger" | "metrics" | "checkout";
  setActiveTab: (tab: "radar" | "ledger" | "metrics" | "checkout") => void;
  connectionState: ConnectionState;
  user: UserContext | null;
  onLogout: () => void;
  onRefresh?: () => void;
}

export default function Header({
  activeTab,
  setActiveTab,
  connectionState,
  user,
  onLogout,
  onRefresh,
}: HeaderProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  // Normalize state
  const isConnected = connectionState === "CONNECTED";
  const isConnecting = connectionState === "CONNECTING";
  const isReconnecting = connectionState === "RECONNECTING" || connectionState === "STALE";

  // Tooltip content based on real connection state
  const getStatusLabel = () => {
    if (isConnected) return "Connected";
    if (isConnecting) return "Connecting";
    if (isReconnecting) return "Reconnecting";
    return "Disconnected";
  };

  const getStatusTooltip = () => {
    if (isConnected) {
      return {
        title: "WebSocket connected",
        description: "Real-time updates",
      };
    }
    if (isConnecting) {
      return {
        title: "Connecting to server",
        description: "Establishing real-time session",
      };
    }
    if (isReconnecting) {
      return {
        title: "Reconnecting to server",
        description: "Attempting to restore real-time connection",
      };
    }
    return {
      title: "WebSocket disconnected",
      description: "Real-time updates unavailable",
    };
  };

  // Derive initials from username or fallback to DG
  const getInitials = (): string => {
    if (!user?.username) return "DG";
    const name = user.username.split("@")[0].replace(/[^a-zA-Z]/g, "");
    if (name.length >= 2) {
      return name.slice(0, 2).toUpperCase();
    }
    return "DG";
  };

  const tooltip = getStatusTooltip();

  return (
    <header className="border-b border-[#1b2436] bg-[#070b16] sticky top-0 z-40 px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand & Navigation */}
        <div className="flex items-center gap-8">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-sm">
              <Shield className="w-4 h-4" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-semibold tracking-tight text-white text-base">RevenueOS</span>
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-[#101726] text-zinc-400 border border-[#223049] tracking-wider">
                DECISION ENGINE
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center gap-6" aria-label="Main Navigation">
            <button
              onClick={() => setActiveTab("radar")}
              className={`text-xs font-medium transition-colors flex items-center gap-2 py-1 relative ${
                activeTab === "radar"
                  ? "text-blue-400 font-semibold after:absolute after:bottom-[-13px] after:left-0 after:right-0 after:h-[2px] after:bg-blue-500"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span>Revenue Radar</span>
            </button>

            <button
              onClick={() => setActiveTab("ledger")}
              className={`text-xs font-medium transition-colors flex items-center gap-2 py-1 relative ${
                activeTab === "ledger"
                  ? "text-blue-400 font-semibold after:absolute after:bottom-[-13px] after:left-0 after:right-0 after:h-[2px] after:bg-blue-500"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Decision Ledger</span>
            </button>

            <button
              onClick={() => setActiveTab("metrics")}
              className={`text-xs font-medium transition-colors flex items-center gap-2 py-1 relative ${
                activeTab === "metrics"
                  ? "text-blue-400 font-semibold after:absolute after:bottom-[-13px] after:left-0 after:right-0 after:h-[2px] after:bg-blue-500"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Outcome Metrics</span>
            </button>

            <button
              onClick={() => setActiveTab("checkout")}
              className={`text-xs font-medium transition-colors flex items-center gap-2 py-1 relative ${
                activeTab === "checkout"
                  ? "text-blue-400 font-semibold after:absolute after:bottom-[-13px] after:left-0 after:right-0 after:h-[2px] after:bg-blue-500"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <CreditCard className="w-3.5 h-3.5" />
              <span>Checkout</span>
            </button>
          </nav>
        </div>

        {/* Top Right Controls */}
        <div className="flex items-center gap-3.5">
          {/* Real WebSocket Status Pill with accessible Tooltip */}
          <div
            className="relative"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onFocus={() => setShowTooltip(true)}
            onBlur={() => setShowTooltip(false)}
          >
            <button
              type="button"
              aria-label={`WebSocket status: ${getStatusLabel()}`}
              className="flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-[#091021] border border-[#1b263b] text-xs transition-colors hover:border-[#273752] cursor-default focus:outline-none focus:ring-1 focus:ring-blue-500/50"
            >
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${
                  isConnected
                    ? "bg-teal-400 shadow-[0_0_8px_rgba(20,184,166,0.6)]"
                    : isConnecting
                    ? "bg-amber-400 animate-ping"
                    : isReconnecting
                    ? "bg-amber-500 animate-pulse"
                    : "bg-red-500"
                }`}
              />
              <div className="flex flex-col text-left">
                <span className="text-zinc-200 text-[11px] font-medium leading-tight">
                  {getStatusLabel()}
                </span>
                <span className="text-[9px] text-zinc-500 leading-tight">
                  {isConnected ? "Real-time stream active" : "Real-time stream inactive"}
                </span>
              </div>
            </button>

            {/* Tooltip Card */}
            {showTooltip && (
              <div className="absolute right-0 top-full mt-2 w-56 p-2.5 rounded-lg bg-[#0e1626] border border-[#223049] shadow-xl z-50 text-left pointer-events-none animate-in fade-in duration-150">
                <div className="text-[11px] font-semibold text-white">
                  {tooltip.title}
                </div>
                <div className="text-[10px] text-zinc-400 mt-0.5 leading-tight">
                  {tooltip.description}
                </div>
              </div>
            )}
          </div>

          {/* Refresh Button */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              title="Refresh telemetry"
              aria-label="Refresh telemetry data"
              className="p-1.5 text-zinc-400 hover:text-white rounded-md hover:bg-[#121a2c] border border-transparent hover:border-[#223049] transition-colors"
            >
              <RotateCw className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Operator Role & Sign Out */}
          <div className="flex items-center gap-2 pl-1 border-l border-[#1b2436]">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-[9px] font-mono uppercase text-amber-400 tracking-wider font-semibold">
                {user?.role || "OPERATOR"}
              </span>
              <button
                onClick={onLogout}
                className="text-[11px] text-zinc-400 hover:text-rose-400 flex items-center gap-1 transition-colors justify-end"
                title="Sign out of operator session"
              >
                <LogOut className="w-3 h-3" />
                <span>Sign out</span>
              </button>
            </div>

            {/* Operator Initials Badge */}
            <div
              title={user ? user.username : "Operator profile"}
              className="w-8 h-8 rounded-full bg-[#141e33] border border-[#273752] flex items-center justify-center text-xs font-semibold text-zinc-200 shrink-0 select-none"
            >
              {getInitials()}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
