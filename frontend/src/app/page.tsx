import { ShieldAlert, Activity, DollarSign, ArrowUpRight } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#0A0D12] text-[#F3F4F6]">
      {/* Top Header */}
      <header className="border-b border-[#1F2430] bg-[#0E121B] px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/30 text-[#F59E0B]">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <span className="text-base font-semibold tracking-tight text-white">RevenueOS</span>
              <span className="ml-2 text-xs font-mono text-[#9CA3AF]">v1.0.0</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#1F2430] px-3 py-1 text-xs font-mono text-[#9CA3AF]">
              <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse"></span>
              WS Standby
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Metric Cards Skeleton */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-[#1F2430] bg-[#121722] p-5">
            <div className="flex items-center justify-between text-[#9CA3AF]">
              <span className="text-xs font-medium uppercase tracking-wider">Revenue at Risk</span>
              <DollarSign className="h-4 w-4" />
            </div>
            <div className="mt-3 text-2xl font-semibold text-white">₹0.00</div>
            <div className="mt-1 text-xs text-[#6B7280]">No active failed payments</div>
          </div>

          <div className="rounded-lg border border-[#1F2430] bg-[#121722] p-5">
            <div className="flex items-center justify-between text-[#9CA3AF]">
              <span className="text-xs font-medium uppercase tracking-wider">Expected Recoverable</span>
              <ArrowUpRight className="h-4 w-4 text-[#F59E0B]" />
            </div>
            <div className="mt-3 text-2xl font-semibold text-white">₹0.00</div>
            <div className="mt-1 text-xs text-[#6B7280]">Calculated via ERV engine</div>
          </div>

          <div className="rounded-lg border border-[#1F2430] bg-[#121722] p-5">
            <div className="flex items-center justify-between text-[#9CA3AF]">
              <span className="text-xs font-medium uppercase tracking-wider">Actually Recovered</span>
              <Activity className="h-4 w-4 text-emerald-500" />
            </div>
            <div className="mt-3 text-2xl font-semibold text-emerald-400">₹0.00</div>
            <div className="mt-1 text-xs text-[#6B7280]">Verified Razorpay outcomes</div>
          </div>

          <div className="rounded-lg border border-[#1F2430] bg-[#121722] p-5">
            <div className="flex items-center justify-between text-[#9CA3AF]">
              <span className="text-xs font-medium uppercase tracking-wider">Incremental Lift</span>
              <span className="text-xs font-mono text-[#F59E0B]">vs Baseline</span>
            </div>
            <div className="mt-3 text-2xl font-semibold text-white">₹0.00</div>
            <div className="mt-1 text-xs text-[#6B7280]">Counterfactual lift (Y - X)</div>
          </div>
        </div>

        {/* Empty State Banner */}
        <div className="mt-8 rounded-lg border border-dashed border-[#262D3D] bg-[#0E121B] p-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#1F2430] text-[#9CA3AF]">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-white">No Payment Data Connected Yet</h3>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#9CA3AF]">
            Connect your Razorpay Test credentials or configure incoming webhooks to begin monitoring and recovering at-risk revenue.
          </p>
        </div>
      </main>
    </div>
  );
}
