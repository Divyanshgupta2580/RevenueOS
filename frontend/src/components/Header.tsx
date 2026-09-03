"use client";

import { Activity, Radio, Shield, LogOut } from "lucide-react";
import type { ConnectionState, UserContext } from "@/lib/types";

interface HeaderProps {
  activeTab: "radar" | "ledger" | "metrics";
  setActiveTab: (tab: "radar" | "ledger" | "metrics") => void;
  connectionState: ConnectionState;
  user: UserContext | null;
  onLogout: () => void;
}

export default function Header({
  activeTab,
  setActiveTab,
  connectionState,
  user,
  onLogout,
}: HeaderProps) {
  const isConnected = connectionState === "CONNECTED";
  const isConnecting = connectionState === "CONNECTING" || connectionState === "STALE";

  return (
    <header className="border-b border-[#21262d] bg-[#0d1117] sticky top-0 z-40 px-6 py-3.5">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand & Badge */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold tracking-tight text-white text-base">RevenueOS</span>
              <span className="ml-2 text-xs font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                DECISION ENGINE
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center gap-1 border-l border-zinc-800 pl-6">
            <button
              onClick={() => setActiveTab("radar")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                activeTab === "radar"
                  ? "bg-zinc-800 text-white border border-zinc-700"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
              }`}
            >
              <Radio className="w-3.5 h-3.5 text-amber-400" />
              Revenue Radar
            </button>
            <button
              onClick={() => setActiveTab("ledger")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                activeTab === "ledger"
                  ? "bg-zinc-800 text-white border border-zinc-700"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
              }`}
            >
              <Activity className="w-3.5 h-3.5 text-blue-400" />
              Decision Ledger
            </button>
            <button
              onClick={() => setActiveTab("metrics")}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
                activeTab === "metrics"
                  ? "bg-zinc-800 text-white border border-zinc-700"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800/50"
              }`}
            >
              Outcome Metrics
            </button>
          </nav>
        </div>

        {/* Status and User Info */}
        <div className="flex items-center gap-4">
          {/* Real-time Connection State */}
          <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? "bg-emerald-400 animate-pulse"
                  : isConnecting
                  ? "bg-amber-400 animate-ping"
                  : "bg-rose-500"
              }`}
            />
            <span className="font-mono text-zinc-300 capitalize text-[11px]">
              {connectionState.toLowerCase()}
            </span>
          </div>

          {/* User badge */}
          {user && (
            <div className="hidden sm:flex items-center gap-2 text-xs text-zinc-400">
              <span className="text-zinc-300 font-medium">{user.username}</span>
              <span className="uppercase text-[10px] px-1.5 py-0.5 bg-zinc-800 rounded border border-zinc-700 font-mono text-amber-400">
                {user.role}
              </span>
            </div>
          )}

          {/* Logout */}
          <button
            onClick={onLogout}
            title="Sign out of RevenueOS"
            className="p-1.5 text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 rounded transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
