/**
 * Razorpay Standard Web Checkout Integration Client.
 *
 * Strictly adheres to fintech security standards:
 * - Public key ONLY on the frontend (NEXT_PUBLIC_RAZORPAY_KEY_ID or order response).
 * - KEY_SECRET is NEVER bundled or exposed.
 * - Orders created via backend POST /api/create-order.
 * - Signatures verified via backend POST /api/verify-payment with HMAC-SHA256.
 */

export interface CreateOrderResponse {
  order_id: string;
  amount: number;
  currency: string;
  status: string;
  key_id?: string;
  receipt?: string;
}

export interface VerifyPaymentResponse {
  status: "success" | "failure";
  verified: boolean;
  message: string;
  order_id: string;
  payment_id: string;
}

export interface RazorpayCheckoutOptions {
  amountPaise: number;
  currency?: string;
  receipt?: string;
  name?: string;
  description?: string;
  customerName?: string;
  customerEmail?: string;
  customerContact?: string;
  paymentReference?: string;
  notes?: Record<string, string>;
  onSuccess?: (result: {
    payment_id: string;
    order_id: string;
    signature: string;
    verification: VerifyPaymentResponse;
  }) => void;
  onDismiss?: () => void;
  onFailure?: (error: { code?: string; description?: string; reason?: string }) => void;
}

export interface RazorpayFailureResponse {
  code?: string;
  description?: string;
  source?: string;
  step?: string;
  reason?: string;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => {
      open: () => void;
      on: (event: string, handler: (response: { error?: RazorpayFailureResponse }) => void) => void;
    };
  }
}

/**
 * Dynamically inject the Razorpay Standard Checkout script if not already present.
 */
export function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") return resolve(false);
    if (window.Razorpay) return resolve(true);

    const existing = document.querySelector<HTMLScriptElement>(
      'script[src="https://checkout.razorpay.com/v1/checkout.js"]'
    );
    if (existing) {
      if (window.Razorpay) return resolve(true);
      existing.addEventListener("load", () => resolve(true));
      existing.addEventListener("error", () => resolve(false));
      return;
    }

    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => {
      console.error("Failed to load Razorpay checkout.js script.");
      resolve(false);
    };
    document.body.appendChild(script);
  });
}

/**
 * Call backend to create a standard order (minimum 100 paise).
 */
export async function createRazorpayOrder(
  amountPaise: number,
  currency = "INR",
  receipt?: string,
  notes?: Record<string, string>
): Promise<CreateOrderResponse> {
  const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";

  const res = await fetch(`${apiOrigin}/api/create-order`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      amount: amountPaise,
      currency,
      receipt: receipt || `rcpt_${Date.now()}`,
      notes: notes || {},
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.message || `Failed to create order (HTTP ${res.status})`);
  }

  return res.json();
}

/**
 * Call backend to verify HMAC-SHA256 signature of completed checkout.
 */
export async function verifyRazorpayPayment(
  orderId: string,
  paymentId: string,
  signature: string,
  paymentReference?: string
): Promise<VerifyPaymentResponse> {
  const apiOrigin = process.env.NEXT_PUBLIC_API_ORIGIN || "http://localhost:8000";

  const res = await fetch(`${apiOrigin}/api/verify-payment`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      razorpay_order_id: orderId,
      razorpay_payment_id: paymentId,
      razorpay_signature: signature,
      payment_reference: paymentReference,
    }),
  });

  const data = await res.json().catch(() => ({
    status: "failure",
    verified: false,
    message: "Unknown server response during verification",
  }));

  if (!res.ok || !data.verified) {
    throw new Error(data.message || "Payment signature verification failed.");
  }

  return data;
}

/**
 * End-to-end checkout launcher:
 * 1. Loads checkout.js
 * 2. Calls /api/create-order
 * 3. Opens Razorpay Modal with order_id and public key
 * 4. On success, calls /api/verify-payment
 * 5. Handles user dismissal & failure events
 */
export async function launchRazorpayCheckout(options: RazorpayCheckoutOptions): Promise<void> {
  const isLoaded = await loadRazorpayScript();
  if (!isLoaded || !window.Razorpay) {
    throw new Error("Unable to load Razorpay payment SDK. Please check internet connection.");
  }

  // 1. Create order on backend
  const order = await createRazorpayOrder(
    options.amountPaise,
    options.currency || "INR",
    options.receipt,
    options.notes
  );

  // 2. Resolve Key ID (prefer environment variable, fallback to order response)
  const keyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || order.key_id;
  if (!keyId) {
    throw new Error("Razorpay Key ID is not configured (NEXT_PUBLIC_RAZORPAY_KEY_ID).");
  }

  // 3. Configure Razorpay modal options
  const rzpOptions = {
    key: keyId,
    amount: order.amount,
    currency: order.currency || "INR",
    name: options.name || "RevenueOS",
    description: options.description || "Revenue Recovery Payment",
    order_id: order.order_id,
    prefill: {
      name: options.customerName || "RevenueOS Operator",
      email: options.customerEmail || "operator@revenueos.local",
      contact: options.customerContact || "9999999999",
    },
    readonly: {
      contact: true,
      email: true,
      name: true,
    },
    theme: {
      color: "#f59e0b", // RevenueOS Amber
    },
    modal: {
      ondismiss: () => {
        if (options.onDismiss) {
          options.onDismiss();
        }
      },
    },
    handler: async (response: {
      razorpay_payment_id: string;
      razorpay_order_id: string;
      razorpay_signature: string;
    }) => {
      try {
        const verification = await verifyRazorpayPayment(
          response.razorpay_order_id,
          response.razorpay_payment_id,
          response.razorpay_signature,
          options.paymentReference
        );
        if (options.onSuccess) {
          options.onSuccess({
            payment_id: response.razorpay_payment_id,
            order_id: response.razorpay_order_id,
            signature: response.razorpay_signature,
            verification,
          });
        }
      } catch (err: unknown) {
        if (options.onFailure) {
          const errMsg = err instanceof Error ? err.message : "Payment verification failed.";
          options.onFailure({
            reason: "VERIFICATION_FAILED",
            description: errMsg,
          });
        }
      }
    },
  };

  const instance = new window.Razorpay(rzpOptions);

  // 4. Listen for payment failure events
  instance.on("payment.failed", (response: { error?: RazorpayFailureResponse }) => {
    const err = response.error || {};
    if (options.onFailure) {
      options.onFailure({
        code: err.code,
        description: err.description || "Payment processing failed.",
        reason: err.reason,
      });
    }
  });

  // 5. Open checkout modal
  instance.open();
}
