"use client";

import Link from "next/link";
import { ArrowLeft, Shield } from "lucide-react";
import RazorpayCheckoutView from "@/components/RazorpayCheckoutView";

export default function CheckoutPage() {
  return (
    <div className="min-h-screen bg-[#08090b] text-[#f3f4f6]">
      {/* Top Navbar */}
      <nav className="border-b border-[#21262d] bg-[#0d1117] px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-1.5 text-zinc-400 hover:text-white rounded-md hover:bg-zinc-800 transition-colors flex items-center gap-1.5 text-xs font-mono"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Dashboard</span>
            </Link>
            <div className="h-4 w-px bg-zinc-800" />
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Shield className="w-3.5 h-3.5" />
              </div>
              <span className="font-semibold tracking-tight text-white text-sm">
                RevenueOS
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                CHECKOUT
              </span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Checkout Container */}
      <main className="py-8">
        <RazorpayCheckoutView />
      </main>
    </div>
  );
}
