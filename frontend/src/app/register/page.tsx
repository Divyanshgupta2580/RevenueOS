"use client";

import { Shield, Lock, Mail, ArrowRight, UserCheck } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import TurnstileWidget from "@/components/TurnstileWidget";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!turnstileToken) {
      setError("Please complete the Cloudflare security verification.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters in length.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match. Please re-enter your password confirmation.");
      return;
    }

    setLoading(true);
    setError(null);

    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";

    try {
      const resp = await fetch(`${apiOrigin}/api/auth/register/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
          confirmPassword,
          turnstileToken,
        }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        setError(data.error?.message || data.message || "Registration failed. Please try again.");
        return;
      }

      // Successful registration -> Redirect to /login with notification
      router.push("/login?registered=1");
    } catch {
      setError("Unable to connect to RevenueOS registration service.");
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
            AI Revenue Recovery Decision Engine &bull; Operator Registration
          </p>
        </div>

        {/* Registration Card */}
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
                  id="email"
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
              <label className="block text-xs font-medium text-zinc-300 mb-1">Password (min. 8 characters)</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a strong password"
                  className="w-full pl-9 pr-3 py-2 bg-zinc-900 border border-zinc-700 rounded-md text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-300 mb-1">Confirm Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="confirmPassword"
                  type="password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
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
                onExpire={() => setTurnstileToken("")}
              />
            </div>

            <button
              type="submit"
              disabled={loading || !turnstileToken}
              className="w-full py-2.5 px-4 rounded-md bg-amber-500 hover:bg-amber-400 text-black font-semibold text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
            >
              {loading ? (
                "Creating Account..."
              ) : (
                <>
                  <UserCheck className="w-3.5 h-3.5" />
                  <span>Create Operator Account</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>

          {/* Link to Login */}
          <div className="mt-5 pt-4 border-t border-zinc-800 text-center">
            <p className="text-xs text-zinc-400">
              Already have an account?{" "}
              <Link
                href="/login"
                className="text-amber-400 hover:text-amber-300 font-medium underline underline-offset-2 transition-colors"
              >
                Sign In
              </Link>
            </p>
          </div>
        </div>

        {/* Security Notice */}
        <p className="text-[11px] text-zinc-500 text-center mt-6">
          Protected by Cloudflare Turnstile &bull; Argon2id Hash Security
        </p>
      </div>
    </div>
  );
}
