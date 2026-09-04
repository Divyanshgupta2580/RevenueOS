"use client";

import { useEffect, useState } from "react";
import {
  CreditCard,
  CheckCircle2,
  XCircle,
  Loader2,
  ShieldCheck,
  ArrowRight,
  Copy,
  Check,
  Info,
  ExternalLink,
  ChevronDown,
} from "lucide-react";
import { launchRazorpayCheckout, VerifyPaymentResponse } from "@/lib/razorpay";
import { formatPaiseToRupees } from "@/lib/format";

interface VerifiedPaymentRecord {
  payment_id: string;
  order_id: string;
  amount: number;
  currency: string;
  status: string;
  signature: string;
  created_at?: string;
}

interface RazorpayCheckoutViewProps {
  initialAmountPaise?: number;
  initialPaymentId?: string;
  onPaymentComplete?: (paymentId: string) => void;
}

export default function RazorpayCheckoutView({
  initialAmountPaise = 10000, // ₹100 default
  initialPaymentId,
  onPaymentComplete,
}: RazorpayCheckoutViewProps) {
  const [amountPaise, setAmountPaise] = useState<number>(initialAmountPaise);
  const [customerEmail, setCustomerEmail] = useState("operator@revenueos.local");
  const [customerContact, setCustomerContact] = useState("9999999999");
  const [notes, setNotes] = useState("Revenue recovery checkout via RevenueOS");
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedSignature, setCopiedSignature] = useState(false);
  const [copiedPaymentId, setCopiedPaymentId] = useState(false);
  const [copiedOrderId, setCopiedOrderId] = useState(false);
  const [isMakingPayment, setIsMakingPayment] = useState(false);

  // Success data from immediate checkout
  const [successData, setSuccessData] = useState<{
    payment_id: string;
    order_id: string;
    signature: string;
    verification: VerifyPaymentResponse;
  } | null>(null);

  // Latest verified payment from server history
  const [latestPayment, setLatestPayment] = useState<VerifiedPaymentRecord | null>(null);

  // Presets matching fintech defaults
  const presets = [
    { label: "₹1.00 (Min)", paise: 100 },
    { label: "₹100.00", paise: 10000 },
    { label: "₹500.00", paise: 50000 },
    { label: "₹1,500.00", paise: 150000 },
    { label: "₹4,999.00", paise: 499900 },
  ];

  // Fetch recent verified payment on mount
  useEffect(() => {
    const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";
    fetch(`${apiOrigin}/api/verify-payment`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.status === "success" && data.payment) {
          setLatestPayment(data.payment);
        }
      })
      .catch(() => {});
  }, []);

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
          setIsMakingPayment(false);

          // Update latest payment state
          setLatestPayment({
            payment_id: res.payment_id,
            order_id: res.order_id,
            amount: amountPaise,
            currency: "INR",
            status: "captured",
            signature: res.signature,
            created_at: new Date().toISOString(),
          });

          if (onPaymentComplete && initialPaymentId) {
            onPaymentComplete(initialPaymentId);
          } else if (onPaymentComplete) {
            onPaymentComplete(res.payment_id);
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

  const handleCopy = (text: string, type: "signature" | "paymentId" | "orderId") => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      if (type === "signature") {
        setCopiedSignature(true);
        setTimeout(() => setCopiedSignature(false), 2000);
      } else if (type === "paymentId") {
        setCopiedPaymentId(true);
        setTimeout(() => setCopiedPaymentId(false), 2000);
      } else if (type === "orderId") {
        setCopiedOrderId(true);
        setTimeout(() => setCopiedOrderId(false), 2000);
      }
    }
  };

  const handleCopySignature = (sig: string) => handleCopy(sig, "signature");

  // Format date cleanly
  const formatTxDate = (dateStr?: string) => {
    try {
      const date = dateStr ? new Date(dateStr) : new Date();
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch {
      return "Recent Transaction";
    }
  };

  // Active verified transaction to display
  const activeTx = successData
    ? {
        payment_id: successData.payment_id,
        order_id: successData.order_id,
        amount: amountPaise,
        signature: successData.signature,
        status: "VERIFIED & CAPTURED",
        created_at: new Date().toISOString(),
      }
    : latestPayment
    ? {
        payment_id: latestPayment.payment_id,
        order_id: latestPayment.order_id,
        amount: latestPayment.amount,
        signature: latestPayment.signature || "Verified via backend HMAC-SHA256 signature validation",
        status: "VERIFIED & CAPTURED",
        created_at: latestPayment.created_at,
      }
    : null;

  // Show verified view if activeTx exists and user hasn't explicitly clicked "Make Another Payment"
  const showVerifiedView = activeTx && !isMakingPayment;

  return (
    <div className="w-full space-y-6">
      {/* Central Razorpay Checkout Card */}
      <div className="bg-[#091021] border border-[#1b263b] rounded-xl p-6 shadow-xl">
        {/* Card Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#162033] pb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
              <CreditCard className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight">
                  Razorpay Standard Web Checkout
                </h2>
                <span className="text-[10px] font-mono font-semibold uppercase px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  TEST MODE
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Standard modal payment gateway integration with server-side HMAC-SHA256 signature verification.
              </p>
            </div>
          </div>

          {/* HMAC Verified Badge */}
          <div className="flex items-center gap-2.5 font-mono text-xs text-teal-400 bg-[#091723] px-3 py-1.5 rounded-lg border border-teal-500/30 shrink-0 cursor-default">
            <ShieldCheck className="w-4 h-4 text-teal-400 shrink-0" />
            <div className="text-left">
              <div className="text-[10px] font-mono text-zinc-400 uppercase tracking-wider leading-none">HMAC-SHA256</div>
              <div className="text-xs font-semibold text-teal-300 mt-0.5">Verified</div>
            </div>
            <ChevronDown className="w-4 h-4 text-zinc-400 ml-1 shrink-0" />
          </div>
        </div>

        {/* State A: Verified & Captured Success State */}
        {showVerifiedView ? (
          <div className="mt-6 space-y-5 animate-in fade-in duration-200">
            {/* Success Alert Banner */}
            <div className="p-4 rounded-xl bg-[#092224] border border-teal-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-teal-500/20 border border-teal-400/40 flex items-center justify-center text-teal-400 shrink-0">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">
                    Payment Verified &amp; Captured Successfully!
                  </div>
                  <div className="text-xs text-teal-300/80 mt-0.5">
                    The payment signature was verified on the backend and the transaction was recorded successfully.
                  </div>
                </div>
              </div>
              <div className="text-left sm:text-right shrink-0">
                <div className="text-xs font-mono text-zinc-300">
                  {formatTxDate(activeTx.created_at)}
                </div>
                <div className="text-[10px] font-mono text-teal-400 mt-0.5">
                  Test Mode Transaction
                </div>
              </div>
            </div>

            {/* Transaction Details Container */}
            <div className="bg-[#070b16] rounded-xl p-5 border border-[#162033]">
              <div className="flex items-center justify-between border-b border-[#141d30] pb-3 mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Transaction Details
                  </h3>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    Verified payment information from Razorpay
                  </p>
                </div>
                <span className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-600/50 text-emerald-400 font-bold text-[10px]">
                  VERIFIED &amp; CAPTURED
                </span>
              </div>

              <div className="space-y-3 font-mono text-xs">
                {/* Status */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 py-1.5 border-b border-[#141d30]">
                  <span className="text-zinc-400 font-sans">Status</span>
                  <span className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-600/50 text-emerald-400 font-bold text-[10px] w-fit">
                    VERIFIED &amp; CAPTURED
                  </span>
                </div>

                {/* Amount Paid */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 py-1.5 border-b border-[#141d30]">
                  <span className="text-zinc-400 font-sans">Amount Paid</span>
                  <span className="text-white font-bold text-sm">
                    {formatPaiseToRupees(activeTx.amount)}
                  </span>
                </div>

                {/* Payment ID */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 py-1.5 border-b border-[#141d30] min-w-0">
                  <span className="text-zinc-400 font-sans">Razorpay Payment ID</span>
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-200 break-all min-w-0">{activeTx.payment_id}</span>
                    <button
                      onClick={() => handleCopy(activeTx.payment_id, "paymentId")}
                      title={copiedPaymentId ? "Copied!" : "Copy Payment ID"}
                      aria-label="Copy Payment ID"
                      className="p-1 text-zinc-400 hover:text-white rounded hover:bg-[#121c2d] transition-colors shrink-0"
                    >
                      {copiedPaymentId ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Order ID */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 py-1.5 border-b border-[#141d30] min-w-0">
                  <span className="text-zinc-400 font-sans">Razorpay Order ID</span>
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-200 break-all min-w-0">{activeTx.order_id}</span>
                    <button
                      onClick={() => handleCopy(activeTx.order_id, "orderId")}
                      title={copiedOrderId ? "Copied!" : "Copy Order ID"}
                      aria-label="Copy Order ID"
                      className="p-1 text-zinc-400 hover:text-white rounded hover:bg-[#121c2d] transition-colors shrink-0"
                    >
                      {copiedOrderId ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                {/* HMAC-SHA256 Signature */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1.5 min-w-0">
                  <span className="text-zinc-400 font-sans shrink-0">HMAC-SHA256 Signature</span>
                  <div className="flex items-center gap-2 bg-[#050812] border border-[#162133] rounded-lg px-3 py-2 text-[11px] text-zinc-400 w-full sm:max-w-xl min-w-0 justify-between overflow-hidden">
                    <span className="truncate font-mono select-all min-w-0">
                      {activeTx.signature}
                    </span>
                    <button
                      onClick={() => handleCopySignature(activeTx.signature)}
                      title={copiedSignature ? "Copied!" : "Copy signature"}
                      aria-label="Copy signature"
                      className="p-1 text-zinc-400 hover:text-white rounded hover:bg-[#121c2d] transition-colors shrink-0 ml-1"
                    >
                      {copiedSignature ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Actions */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
              <button
                onClick={() => setIsMakingPayment(true)}
                className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shadow-md shadow-blue-900/30 w-fit"
              >
                <CreditCard className="w-4 h-4" />
                <span>Make Another Payment</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>

              <div className="flex items-center gap-2 text-xs text-zinc-400">
                <Info className="w-4 h-4 text-blue-400 shrink-0" />
                <span>This is a test transaction. No real money has been charged.</span>
              </div>
            </div>
          </div>
        ) : (
          /* State B: Interactive Checkout Form */
          <div className="mt-6 space-y-6 animate-in fade-in duration-200">
            {/* Amount Selection */}
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-zinc-400 mb-2 font-medium">
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
                        ? "bg-blue-600 text-white font-bold shadow-md shadow-blue-900/40 border border-blue-400"
                        : "bg-[#0c1424] hover:bg-[#111c33] text-zinc-300 border border-[#1b263b]"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-zinc-400">Custom Paise:</span>
                <input
                  type="number"
                  min="100"
                  step="100"
                  value={amountPaise}
                  onChange={(e) => setAmountPaise(Math.max(100, parseInt(e.target.value) || 100))}
                  className="bg-[#0c1424] border border-[#1b263b] rounded px-3 py-1.5 text-xs font-mono text-white w-36 focus:outline-none focus:border-blue-500"
                />
                <span className="text-xs font-mono text-blue-400 font-bold">
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
                  className="w-full bg-[#0c1424] border border-[#1b263b] rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 font-mono"
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
                  className="w-full bg-[#0c1424] border border-[#1b263b] rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 font-mono"
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
                className="w-full bg-[#0c1424] border border-[#1b263b] rounded px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                placeholder="Recovery description or payment note"
              />
            </div>

            {/* Status / Error feedback */}
            {statusMessage && (
              <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-300 text-xs flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
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
            <div className="pt-2 flex flex-col sm:flex-row sm:items-center gap-4">
              <button
                type="button"
                onClick={handleCheckout}
                disabled={loading}
                className="py-3 px-6 rounded-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold text-xs tracking-wide transition-all shadow-lg shadow-blue-900/30 disabled:opacity-50 flex items-center justify-center gap-2 w-full sm:w-auto"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin text-white" />
                    <span>Processing with Razorpay...</span>
                  </>
                ) : (
                  <>
                    <CreditCard className="w-4 h-4" />
                    <span>Pay {formatPaiseToRupees(amountPaise)} with Razorpay</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              {activeTx && (
                <button
                  type="button"
                  onClick={() => setIsMakingPayment(false)}
                  className="text-xs text-zinc-400 hover:text-zinc-200 underline transition-colors"
                >
                  View Last Verified Transaction
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 text-[11px] text-zinc-500 pt-1">
              <Info className="w-3.5 h-3.5 text-blue-400 shrink-0" />
              <span>Opens the standard Razorpay checkout modal with test card / UPI support. No real money will be charged.</span>
            </div>
          </div>
        )}
      </div>

      {/* Integration Reference Card */}
      <div className="bg-[#091021]/60 border border-[#1b263b] rounded-xl p-5 text-xs text-zinc-400">
        <h4 className="font-semibold text-zinc-300 mb-2 flex items-center gap-2">
          <span>Standard Checkout Architecture Flow</span>
          <ExternalLink className="w-3.5 h-3.5 text-zinc-500" />
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
          <div className="bg-[#070b16] p-3 rounded-lg border border-[#162033]">
            <span className="font-mono text-blue-400 font-bold text-[11px] block mb-1">
              1. Create Order
            </span>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Frontend calls backend <code className="text-zinc-300">POST /api/create-order</code> with amount &ge; 100 paise. Backend calls Razorpay orders API.
            </p>
          </div>
          <div className="bg-[#070b16] p-3 rounded-lg border border-[#162033]">
            <span className="font-mono text-amber-400 font-bold text-[11px] block mb-1">
              2. Open Modal
            </span>
            <p className="text-[11px] text-zinc-400 leading-relaxed">
              Opens <code className="text-zinc-300">checkout.js</code> modal with <code className="text-zinc-300">order_id</code> and public key. Handles dismissal &amp; failure callbacks.
            </p>
          </div>
          <div className="bg-[#070b16] p-3 rounded-lg border border-[#162033]">
            <span className="font-mono text-teal-400 font-bold text-[11px] block mb-1">
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
