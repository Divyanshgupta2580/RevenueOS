"use client";

import { useState } from "react";
import {
  CreditCard,
  CheckCircle2,
  XCircle,
  Loader2,
  ShieldCheck,
  ArrowRight,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { launchRazorpayCheckout, VerifyPaymentResponse } from "@/lib/razorpay";
import { formatPaiseToRupees } from "@/lib/format";

interface RazorpayCheckoutViewProps {
  initialAmountPaise?: number;
  initialPaymentId?: string;
  onPaymentComplete?: (paymentId: string) => void;
}

export default function RazorpayCheckoutView({
  initialAmountPaise = 50000, // ₹500 default
  initialPaymentId,
  onPaymentComplete,
}: RazorpayCheckoutViewProps) {
  const [amountPaise, setAmountPaise] = useState<number>(initialAmountPaise);
  const [customerEmail, setCustomerEmail] = useState("operator@revenueos.local");
  const [customerContact, setCustomerContact] = useState("9876543210");
  const [notes, setNotes] = useState("Revenue recovery checkout via RevenueOS");
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<{
    payment_id: string;
    order_id: string;
    signature: string;
    verification: VerifyPaymentResponse;
  } | null>(null);

  const presets = [
    { label: "₹1.00 (Min)", paise: 100 },
    { label: "₹100.00", paise: 10000 },
    { label: "₹500.00", paise: 50000 },
    { label: "₹1,500.00", paise: 150000 },
    { label: "₹4,999.00", paise: 499900 },
  ];

  const handleCheckout = async () => {
    if (amountPaise < 100) {
      setError("Minimum checkout amount is 100 paise (₹1.00).");
      return;
    }

    setLoading(true);
    setError(null);
    setStatusMessage("Creating secure order on backend...");

    try {
      await launchRazorpayCheckout({
        amountPaise,
        currency: "INR",
        name: "RevenueOS Checkout",
        description: `Recovery Payment (${formatPaiseToRupees(amountPaise)})`,
        customerEmail,
        customerContact,
        paymentReference: initialPaymentId,
        notes: { note: notes },
        onSuccess: (res) => {
          setLoading(false);
          setStatusMessage(null);
          setSuccessData(res);
          if (onPaymentComplete && initialPaymentId) {
            onPaymentComplete(initialPaymentId);
          }
        },
        onDismiss: () => {
          setLoading(false);
          setStatusMessage(null);
          setError("Payment modal closed. The transaction was cancelled by user.");
        },
        onFailure: (err) => {
          setLoading(false);
          setStatusMessage(null);
          setError(
            err.description ||
              `Payment failed: ${err.reason || err.code || "Transaction declined"}`
          );
        },
      });
    } catch (err: unknown) {
      setLoading(false);
      setStatusMessage(null);
      const errMsg = err instanceof Error ? err.message : "Failed to initiate Razorpay checkout.";
      setError(errMsg);
    }
  };

  const handleReset = () => {
    setSuccessData(null);
    setError(null);
    setStatusMessage(null);
  };

  return (
    <div className="max-w-3xl mx-auto py-6 px-4">
      {/* Header Banner */}
      <div className="bg-[#0e1117] border border-[#21262d] rounded-xl p-6 mb-6 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#21262d] pb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
                Razorpay Standard Web Checkout
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-700/50">
                  Test Mode
                </span>
              </h2>
              <p className="text-xs text-zinc-400 mt-0.5">
                Standard modal payment gateway integration with server-side HMAC-SHA256 signature verification.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs text-zinc-400 bg-zinc-900 px-3 py-1.5 rounded-lg border border-zinc-800">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>HMAC-SHA256 Verified</span>
          </div>
        </div>

        {/* Success View */}
        {successData ? (
          <div className="mt-6 p-6 rounded-lg bg-emerald-950/30 border border-emerald-500/30 text-emerald-200">
            <div className="flex items-center gap-2.5 text-emerald-400 text-base font-semibold mb-2">
              <CheckCircle2 className="w-5 h-5" />
              Payment Verified & Captured Successfully!
            </div>
            <p className="text-xs text-emerald-300/80 mb-5">
              The payment signature was verified on the backend via HMAC-SHA256(order_id + &quot;|&quot; + payment_id, KEY_SECRET).
            </p>

            <div className="bg-black/40 rounded-lg p-4 font-mono text-xs space-y-2 border border-emerald-500/20 text-zinc-300">
              <div className="flex justify-between border-b border-zinc-800 pb-2">
                <span className="text-zinc-500">Status:</span>
                <span className="text-emerald-400 font-bold">VERIFIED &amp; CAPTURED</span>
              </div>
              <div className="flex justify-between border-b border-zinc-800 pb-2">
                <span className="text-zinc-500">Amount Paid:</span>
                <span className="text-white font-bold">{formatPaiseToRupees(amountPaise)}</span>
              </div>
              <div className="flex justify-between border-b border-zinc-800 pb-2">
                <span className="text-zinc-500">Razorpay Payment ID:</span>
                <span className="text-zinc-200">{successData.payment_id}</span>
              </div>
              <div className="flex justify-between border-b border-zinc-800 pb-2">
                <span className="text-zinc-500">Razorpay Order ID:</span>
                <span className="text-zinc-200">{successData.order_id}</span>
              </div>
              <div className="flex flex-col gap-1 pt-1">
                <span className="text-zinc-500">HMAC-SHA256 Signature:</span>
                <span className="text-zinc-400 break-all text-[11px] bg-zinc-950 p-2 rounded border border-zinc-800">
                  {successData.signature}
                </span>
              </div>
            </div>

            <div className="mt-5 flex gap-3">
              <button
                onClick={handleReset}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Make Another Payment
              </button>
            </div>
          </div>
        ) : (
          /* Checkout Form */
          <div className="mt-6 space-y-6">
            {/* Amount Selection */}
            <div>
              <label className="block text-xs font-mono uppercase text-zinc-400 mb-2">
                Select Amount (INR)
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3">
                {presets.map((p) => (
                  <button
                    key={p.paise}
                    type="button"
                    onClick={() => setAmountPaise(p.paise)}
                    className={`py-2 px-3 rounded-lg text-xs font-mono font-medium transition-all ${
                      amountPaise === p.paise
                        ? "bg-amber-500 text-black font-bold shadow-md shadow-amber-500/20"
                        : "bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <span className="text-sm font-mono text-zinc-400">Custom Paise:</span>
                <input
                  type="number"
                  min="100"
                  step="100"
                  value={amountPaise}
                  onChange={(e) => setAmountPaise(Math.max(100, parseInt(e.target.value) || 100))}
                  className="bg-zinc-900 border border-zinc-700 rounded px-3 py-1.5 text-xs font-mono text-white w-40 focus:outline-none focus:border-amber-500"
                />
                <span className="text-xs font-mono text-amber-400 font-bold">
                  = {formatPaiseToRupees(amountPaise)}
                </span>
              </div>
            </div>

            {/* Customer Information (Prefill) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  Customer Email (Prefill)
                </label>
                <input
                  type="email"
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
                  placeholder="customer@example.com"
                />
              </div>
              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  Customer Phone (Prefill)
                </label>
                <input
                  type="tel"
                  value={customerContact}
                  onChange={(e) => setCustomerContact(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
                  placeholder="9876543210"
                />
              </div>
            </div>

            {/* Notes / Reference */}
            <div>
              <label className="block text-xs font-mono text-zinc-400 mb-1">
                Transaction Notes / Reference
              </label>
              <input
                type="text"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-amber-500"
                placeholder="Recovery description or payment note"
              />
            </div>

            {/* Status / Error feedback */}
            {statusMessage && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-300 text-xs flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                {statusMessage}
              </div>
            )}

            {error && (
              <div className="p-3 bg-rose-950/30 border border-rose-500/30 rounded-lg text-rose-300 text-xs flex items-start gap-2">
                <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold">Transaction Notice</div>
                  <div className="text-rose-200/90 mt-0.5">{error}</div>
                </div>
              </div>
            )}

            {/* Pay Button */}
            <div className="pt-2">
              <button
                type="button"
                onClick={handleCheckout}
                disabled={loading}
                className="w-full py-3 px-6 rounded-lg bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-black font-bold text-sm tracking-wide transition-all shadow-lg shadow-amber-500/10 hover:shadow-amber-500/20 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-black" />
                    <span>Processing with Razorpay...</span>
                  </>
                ) : (
                  <>
                    <span>Pay {formatPaiseToRupees(amountPaise)} with Razorpay</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
              <p className="text-[11px] text-zinc-500 text-center mt-2">
                Opens the standard Razorpay checkout modal with test card / UPI support.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Integration Reference card */}
      <div className="bg-[#0e1117]/60 border border-[#21262d] rounded-xl p-5 text-xs text-zinc-400">
        <h4 className="font-semibold text-zinc-300 mb-2 flex items-center gap-2">
          <span>Standard Checkout Architecture Flow</span>
          <ExternalLink className="w-3.5 h-3.5 text-zinc-500" />
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
          <div className="bg-zinc-950/70 p-3 rounded-lg border border-zinc-800">
            <span className="font-mono text-amber-400 font-bold text-[11px] block mb-1">
              1. Create Order
            </span>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Frontend calls backend <code className="text-zinc-300">POST /api/create-order</code> with amount &ge; 100 paise. Backend calls Razorpay orders API.
            </p>
          </div>
          <div className="bg-zinc-950/70 p-3 rounded-lg border border-zinc-800">
            <span className="font-mono text-blue-400 font-bold text-[11px] block mb-1">
              2. Open Modal
            </span>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Opens <code className="text-zinc-300">checkout.js</code> modal with <code className="text-zinc-300">order_id</code> and public key. Handles dismissal &amp; failure callbacks.
            </p>
          </div>
          <div className="bg-zinc-950/70 p-3 rounded-lg border border-zinc-800">
            <span className="font-mono text-emerald-400 font-bold text-[11px] block mb-1">
              3. Verify HMAC
            </span>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Frontend sends payment ID, order ID, and signature to <code className="text-zinc-300">POST /api/verify-payment</code> for cryptographic verification.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
