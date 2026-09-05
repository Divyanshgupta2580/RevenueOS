"use client";

import { Shield, Lock, Mail, ArrowRight, CheckCircle2 } from "lucide-react";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isJustRegistered = searchParams.get("registered") === "1" || searchParams.get("registered") === "true";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";

    try {
      const resp = await fetch(`${apiOrigin}/api/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          username: email,
          password,
        }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        setError(data.error?.message || data.message || "Invalid credentials or authentication failure.");
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
    <div className="w-full max-w-sm">
      {/* Brand Header */}
      <div className="text-center mb-8">
        <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mx-auto mb-3 shadow-lg shadow-amber-500/5">
          <Shield className="w-6 h-6" />
        </div>
        <h1 className="text-xl font-bold tracking-tight text-white">RevenueOS</h1>
        <p className="text-xs text-zinc-400 mt-1">
          AI Revenue Recovery Decision Engine &bull; Operator Sign In
        </p>
      </div>

      {/* Login Card */}
      <div className="bg-[#0e1117] border border-[#21262d] rounded-xl p-6 shadow-xl">
        {isJustRegistered && (
          <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-md text-xs text-emerald-300 font-medium flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Registration successful! Please sign in with your credentials.</span>
          </div>
        )}

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
                placeholder="operator@example.com"
                className="w-full pl-9 pr-3 py-2 bg-zinc-900 border border-zinc-700 rounded-md text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="w-full pl-9 pr-3 py-2 bg-zinc-900 border border-zinc-700 rounded-md text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500 transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-md bg-amber-500 hover:bg-amber-400 text-black font-semibold text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-4"
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

        {/* Link to Register */}
        <div className="mt-5 pt-4 border-t border-zinc-800 text-center">
          <p className="text-xs text-zinc-400">
            Need an operator account?{" "}
            <Link
              href="/register"
              className="text-amber-400 hover:text-amber-300 font-medium underline underline-offset-2 transition-colors"
            >
              Register here
            </Link>
          </p>
        </div>
      </div>

      {/* Security Notice */}
      <p className="text-[11px] text-zinc-500 text-center mt-6">
        Protected by Argon2id Hash &bull; Session Security
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-[#08090b] flex flex-col justify-center items-center p-4">
      <Suspense fallback={<div className="text-zinc-500 text-xs">Loading login...</div>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
