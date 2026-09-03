"use client";

import { Shield, Lock, Mail, ArrowRight } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import TurnstileWidget from "@/components/TurnstileWidget";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@revenueos.local");
  const [password, setPassword] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!turnstileToken) {
      setError("Please complete the Cloudflare security verification.");
      return;
    }

    setLoading(true);
    setError(null);

    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://127.0.0.1:8000";

    try {
      const resp = await fetch(`${apiOrigin}/api/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username: email,
          password,
          turnstileToken,
        }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        setError(data.message || "Invalid credentials or authentication failure.");
        return;
      }

      // Successful login -> Redirect to Command Center
      router.push("/");
    } catch {
      setError("Unable to connect to RevenueOS authentication service.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#08090b] flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-sm">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mx-auto mb-3 shadow-lg shadow-amber-500/5">
            <Shield className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">RevenueOS</h1>
          <p className="text-xs text-zinc-400 mt-1">
            AI Revenue Recovery Decision Engine &bull; Operator Access
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-[#0e1117] border border-[#21262d] rounded-xl p-6 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-md text-xs text-rose-400 font-medium leading-relaxed">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1">Operator Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="operator@revenueos.local"
                  className="w-full pl-9 pr-3 py-2 bg-zinc-900 border border-zinc-700 rounded-md text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter operator password"
                  className="w-full pl-9 pr-3 py-2 bg-zinc-900 border border-zinc-700 rounded-md text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
                />
              </div>
            </div>

            {/* Cloudflare Turnstile Bot Protection */}
            <div className="pt-1">
              <label className="block text-[11px] font-medium text-zinc-400 text-center mb-1">
                Bot Verification
              </label>
              <TurnstileWidget
                onSuccess={(token) => {
                  setTurnstileToken(token);
                  setError(null);
                }}
                onError={() => setError("Turnstile verification failed. Please refresh.")}
              />
            </div>

            <button
              type="submit"
              disabled={loading || !turnstileToken}
              className="w-full py-2.5 px-4 rounded-md bg-amber-500 hover:bg-amber-400 text-black font-semibold text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
            >
              {loading ? (
                "Authenticating..."
              ) : (
                <>
                  Sign In to RevenueOS
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Security Notice */}
        <p className="text-[11px] text-zinc-500 text-center mt-6">
          Protected by Cloudflare Turnstile &bull; Argon2id Session Security
        </p>
      </div>
    </div>
  );
}
