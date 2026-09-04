# RevenueOS — System Architecture Specification

## 1. Executive Summary & Product Thesis

**RevenueOS** is an autonomous AI Revenue Recovery Decision Engine built specifically for the **Razorpay AI Buildathon 2026 (Track 03: AI Revenue Recovery)**.

### The Core Problem
In standard payment ecosystems, failed or at-risk transactions are either abandoned or subjected to blind, programmatic retries. This creates two distinct failure modes:
1. **Dumb retries:** Blindly firing automated retries against hard-declined cards (e.g., lost card, stolen card, fraudulent card) increases processor fees, inflates decline rates, and risks merchant account penalties.
2. **Passive abandonment:** Temporary failures (e.g., soft declines, intermittent bank downtime, insufficient balance, network drops) are abandoned without intelligent, timed follow-ups or alternative channel activations.

### The RevenueOS Solution
RevenueOS answers four questions deterministically:
1. **Identify:** Which revenue is genuinely at risk and recoverable?
2. **Prioritize:** In what order should opportunities be pursued to maximize recovered capital while preserving customer goodwill?
3. **Decide:** What is the optimal, bounded recovery action (`RETRY`, `PAYMENT_LINK`, `REMINDER`, `STOP`) given transaction metadata, customer history, and failure taxonomy?
4. **Execute & Measure:** Does the action satisfy deterministic safety policies? If authorized, execute via Razorpay Test APIs, ingest real asynchronous payment outcomes via signed webhooks, and compute true incremental revenue against a measured baseline.

```
                    ┌────────────────────────────────────────────────────────┐
                    │                      REVENUEOS                         │
                    │               Modular Fintech Monolith                 │
                    └──────────────────────────┬─────────────────────────────┘
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
┌─────────────────────────────┐                                 ┌─────────────────────────────┐
│      Next.js Frontend       │                                 │     Django ASGI Backend     │
│   (Vercel Edge / Server)    │                                 │    (Render Web Service)     │
│                             │                                 │                             │
│ • Dark Fintech Dashboard    │◄────── Authenticated WSS ──────►│ • Django Channels Consumer  │
│ • Real-time Metrics         │        (Application RPC)        │ • In-Memory Channel Layer   │
│ • Opportunity Detail        │                                 │ • PyMongo Data Access Layer │
│ • Audit Decision Ledger     │─────── HTTPS Auth / Turnstile ─►│ • Turnstile Server Guard    │
└─────────────────────────────┘                                 └──────────────┬──────────────┘
                                                                               │
                                       ┌───────────────────────────────────────┼───────────────────────────────────────┐
                                       ▼                                       ▼                                       ▼
                        ┌─────────────────────────────┐         ┌─────────────────────────────┐         ┌─────────────────────────────┐
                        │     Google Gemini API       │         │    Razorpay Test Platform   │         │     MongoDB Atlas (Free)    │
                        │   (Official GenAI SDK)      │         │     (REST APIs & Webhooks)  │         │                             │
                        │                             │         │                             │         │ • users & sessions          │
                        │ • Single Decision Engine    │         │ • Test API Invocations      │         │ • payments (integer paise)  │
                        │ • Bounded Structured JSON   │         │ • Signed Webhook Callbacks  │         │ • recovery_decisions        │
                        │ • Strict Schema Validation  │         │ • Idempotent Execution      │         │ • recovery_actions          │
                        └─────────────────────────────┘         └─────────────────────────────┘         │ • webhook_events            │
                                                                                                        └─────────────────────────────┘
```

---

## 2. Fundamental Architectural Principles

1. **Modular Monolith over Microservices:** RevenueOS runs as a single, highly cohesive backend service (Django + Channels + Uvicorn) paired with a modern Next.js client. No distributed network hops, no Kafka, no microservices overhead.
2. **Zero Floating-Point Money:** All financial transactions and calculations operate exclusively on integer minor currency units (e.g., INR paise: `1 INR = 100 paise`). Floats are strictly prohibited in the business and persistence layers.
3. **AI Recommends, Rules Authorize:** The LLM (Google Gemini) is an advisory engine, never an execution authority. Every AI recommendation must be validated against a deterministic Guarded Autopilot policy layer before any financial action is taken.
4. **WebSocket-First Application Transport:** Standard web dashboards suffer from polling lag or stale state. RevenueOS uses a persistent, authenticated WebSocket connection for all interactive user operations, real-time opportunity updates, and ledger notifications.
5. **Deterministic Baseline Measurement:** RevenueOS does not fabricate recovery claims. If no data exists, a truthful empty state is rendered. Incremental recovery ($Y - X$) is computed by comparing actual recovery against a documented, deterministic control heuristic.
6. **Strict Free-Tier Compatibility:** Operates completely within the free allocations of MongoDB Atlas (512MB), Render (Web Service), Vercel (Hobby), Cloudflare Turnstile, Razorpay Test Mode, and Gemini API.

---

## 3. Technology Stack & Decision Justifications

| Layer | Selected Technology | Why Chosen | What Was Explicitly Rejected & Why |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | **Next.js 15+ (App Router)** | Server-side rendering, strict TypeScript support, optimized asset delivery, zero-config Vercel deployment. | Traditional SPAs (Create React App/Vite standalone) lack seamless SSR and modern route-level layout semantics. |
| **Styling & UI** | **Tailwind CSS + Lucide React** | Low-overhead utility CSS, fast compilation, strict design token control. Lucide provides semantic fintech icons. | Material UI / Chakra UI / AntD (heavy bundle size, inconsistent dark themes, excess CSS-in-JS runtime). |
| **Backend Framework** | **Django 5+ & Django Channels** | Rock-solid request lifecycle, built-in security middleware, battle-tested ASGI Channels implementation for WebSockets. | FastAPI (lacks built-in auth middleware robustness for sessions), Flask (poor native WebSocket integration). |
| **ASGI Server** | **Uvicorn** | Fast, compliant ASGI 3.0 server supporting both HTTP and WebSocket protocols under a single port. | Daphne (slower event loop), Gunicorn alone (does not handle WebSockets natively without Uvicorn workers). |
| **Database Driver** | **PyMongo directly** | Pure, lightweight, direct document manipulation without ORM overhead. Optimal for MongoDB Atlas free tier. | MongoEngine / Mongoose (brittle schema layers, memory bloat), Django ORM (unnatural mapping for document databases). |
| **AI Decision Engine**| **Google GenAI Python SDK (`google-genai`)** | Native Google Gemini SDK, strict schema enforcement via Pydantic/dataclasses, low latency. | LangChain / LangGraph / CrewAI (excess abstractions, fragile prompt templates, unnecessary token overhead). |
| **Payment Gateway** | **Razorpay Test APIs & Webhooks** | Official Razorpay REST APIs for payment link generation and payment fetching; cryptographic webhook verification. | Mock gateway libraries (we interact with real Razorpay Test sandbox). |
| **Authentication** | **Argon2id + HTTP-only Cookies** | Memory-hard password hashing (OWASP recommended); cookies prevent XSS exfiltration of session credentials. | JWT in localStorage (vulnerable to XSS theft, cannot be easily revoked centrally). |
| **Anti-Bot Security** | **Cloudflare Turnstile** | Modern, privacy-preserving CAPTCHA replacement. Verified server-side via Cloudflare Secret Key. | Obfuscated canvas text / puzzles (easily bypassed by OCR/LLMs, poor user accessibility). |

---

## 4. Repository Structure

```
RevenueOS/
├── .github/
│   └── workflows/
│       ├── frontend.yml         # Lint, type-check, build verification
│       └── backend.yml          # Ruff, mypy, pytest suite
├── docs/
│   ├── ARCHITECTURE.md          # This system architecture specification
│   ├── WEBSOCKET_PROTOCOL.md    # Complete WebSocket envelope and message schema
│   ├── DEPLOYMENT.md           # Render and Vercel production runbooks
│   └── EVALUATION.md           # Recovery algorithms and baseline benchmarking
├── backend/
│   ├── manage.py
│   ├── pyproject.toml          # Ruff, pytest, mypy configuration
│   ├── requirements.txt        # Frozen dependencies
│   ├── revenueos/              # Project core
│   │   ├── __init__.py
│   │   ├── asgi.py             # ASGI application entrypoint (HTTP + Channels)
│   │   ├── settings.py         # 12-factor configuration via environment
│   │   ├── urls.py             # HTTP endpoints (health, auth, webhooks)
│   │   └── ws_urls.py          # WebSocket route definitions
│   └── apps/
│       ├── core/               # Shared utilities, money math, exceptions
│       │   ├── exceptions.py
│       │   └── money.py        # Integer minor currency utilities (paise)
│       ├── authentication/     # User auth, Argon2id, Turnstile validation
│       │   ├── services.py
│       │   └── views.py
│       ├── database/           # PyMongo client singleton, indexes, repositories
│       │   ├── client.py
│       │   └── repositories.py
│       ├── radar/              # Revenue Radar scoring & opportunity ranking
│       │   ├── engine.py
│       │   └── models.py
│       ├── brain/              # Gemini AI client, structured output schemas
│       │   ├── client.py
│       │   └── schemas.py
│       ├── policy/             # Guarded Autopilot deterministic policy engine
│       │   ├── engine.py
│       │   └── rules.py
│       ├── razorpay_adapter/   # Isolated Razorpay Test REST client
│       │   └── client.py
│       ├── webhooks/           # Razorpay webhook HMAC verification & ingestion
│       │   └── views.py
│       ├── websocket/          # Channels consumer, protocol routing, heartbeat
│       │   └── consumer.py
│       └── metrics/            # Outcome measurement & counterfactual calculations
│           └── calculator.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── next.config.ts
│   └── src/
│       ├── app/                # App Router pages
│       │   ├── layout.tsx      # Dark root layout, font definitions
│       │   ├── page.tsx        # Command Center dashboard
│       │   ├── login/
│       │   │   └── page.tsx    # Turnstile login screen
│       │   ├── opportunities/
│       │   │   └── [id]/
│       │   │       └── page.tsx # Deep-dive Opportunity view
│       │   ├── ledger/
│       │   │   └── page.tsx    # Audit Decision Ledger
│       │   └── metrics/
│       │       └── page.tsx    # Empirical Outcome Measurement
│       ├── components/         # High-density dark UI components
│       │   ├── ui/             # Buttons, badges, tables, modals
│       │   ├── Header.tsx
│       │   ├── Navigation.tsx
│       │   └── ConnectionStatus.tsx
│       ├── lib/
│       │   ├── api.ts          # HTTP client for login/logout/health
│       │   ├── ws.ts           # Resilient WebSocket client singleton
│       │   ├── money.ts        # Currency formatting for INR paise
│       │   └── types.ts        # Shared TypeScript interfaces
│       └── hooks/
│           ├── useWebSocket.ts
│           └── useAuth.ts
├── .env.example                # Canonical template for all environment variables
└── README.md                   # Project overview, installation, evaluation
```

---

## 5. Data Architecture (MongoDB Schema)

All data access uses `PyMongo` directly. Collections are indexed for fast lookup and strict idempotency.

### 5.1 Collections

#### `users`
Stores authenticated operator credentials.
```json
{
  "_id": "ObjectId",
  "username": "admin@revenueos.internal",
  "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$...",
  "role": "operator",
  "created_at": "2026-09-03T18:00:00Z",
  "last_login": "2026-09-03T18:30:00Z"
}
```
*Index:* `username` (Unique).

#### `sessions`
Server-side authenticated session storage.
```json
{
  "_id": "ObjectId",
  "session_token": "hex_string_64_bytes",
  "user_id": "ObjectId",
  "created_at": "2026-09-03T18:30:00Z",
  "expires_at": "2026-09-04T18:30:00Z",
  "ip_address": "192.0.2.1",
  "user_agent": "Mozilla/5.0..."
}
```
*Indexes:* `session_token` (Unique), `expires_at` (TTL index for automatic cleanup).

#### `payments`
Source-of-truth records for revenue transactions.
```json
{
  "_id": "ObjectId",
  "payment_id": "pay_test_99214A",
  "order_id": "order_test_412",
  "customer_id": "cust_8812",
  "customer_email": "customer@example.com",
  "amount": 499900,
  "currency": "INR",
  "status": "failed",
  "error_code": "BAD_REQUEST_ERROR",
  "error_description": "Card has insufficient funds",
  "failure_reason": "insufficient_funds",
  "failure_category": "soft_decline",
  "retry_count": 1,
  "max_retries_allowed": 3,
  "created_at": "2026-09-03T14:10:00Z",
  "updated_at": "2026-09-03T14:15:00Z",
  "recovery_status": "in_review",
  "last_recovery_action_id": null
}
```
*Indexes:* `payment_id` (Unique), `status`, `recovery_status`, `updated_at`.

#### `recovery_decisions`
Audit log of every AI recommendation and subsequent policy authorization.
```json
{
  "_id": "ObjectId",
  "decision_id": "dec_01J6XYZ",
  "payment_id": "pay_test_99214A",
  "model_version": "gemini-3.6-flash",
  "ai_recommendation": {
    "action": "PAYMENT_LINK",
    "confidence": 0.88,
    "expected_recovery_value": 399920,
    "reason": "Insufficient balance failure with low retry history. Issuing an alternative payment link provides high recovery probability without card strain.",
    "supporting_factors": ["High order value", "Soft decline failure code", "Single previous attempt"],
    "risk_factors": ["Customer notification fatigue if sent repeatedly"]
  },
  "policy_decision": {
    "status": "APPROVED",
    "authorized_action": "PAYMENT_LINK",
    "evaluated_rules": [
      {"rule": "eligibility_check", "passed": true},
      {"rule": "retry_limit_check", "passed": true},
      {"rule": "idempotency_check", "passed": true},
      {"rule": "minor_unit_amount_valid", "passed": true}
    ],
    "evaluated_at": "2026-09-03T14:16:02Z",
    "operator_id": "ObjectId"
  },
  "created_at": "2026-09-03T14:16:02Z"
}
```
*Indexes:* `decision_id` (Unique), `payment_id`, `created_at`.

#### `recovery_actions`
Executions of authorized recovery actions.
```json
{
  "_id": "ObjectId",
  "action_id": "act_01J6ABC",
  "decision_id": "dec_01J6XYZ",
  "payment_id": "pay_test_99214A",
  "action_type": "PAYMENT_LINK",
  "idempotency_key": "idemp_pay_test_99214A_PAYMENT_LINK_1",
  "status": "EXECUTED",
  "external_reference": "plink_test_77812",
  "payload": {
    "amount": 499900,
    "currency": "INR",
    "reference_id": "pay_test_99214A"
  },
  "result": {
    "short_url": "https://rzp.io/i/testlink1"
  },
  "executed_at": "2026-09-03T14:16:05Z",
  "outcome": "PENDING"
}
```
*Indexes:* `action_id` (Unique), `idempotency_key` (Unique), `payment_id`, `status`.

#### `webhook_events`
Ingested Razorpay webhook payloads with cryptographic verification and idempotency check.
```json
{
  "_id": "ObjectId",
  "event_id": "evt_test_rzp_9901",
  "event_type": "payment_link.paid",
  "payment_id": "pay_test_99214A",
  "received_at": "2026-09-03T14:30:10Z",
  "processed": true,
  "processed_at": "2026-09-03T14:30:11Z",
  "signature_valid": true,
  "payload_summary": {
    "amount_paid": 499900,
    "payment_id": "pay_test_99214A_recovered"
  }
}
```
*Indexes:* `event_id` (Unique), `payment_id`, `received_at`.

---

## 6. Mathematical Foundations & Revenue Radar

### 6.1 Integer Minor Currency Unit Rule
To eliminate IEEE-754 floating-point rounding errors in financial transactions:
$$\text{paise} \in \mathbb{Z}_{\ge 0}$$
- `₹10.50` is stored and computed strictly as `1050`.
- All multipliers (probabilities, percentage fees) use integer basis points or exact fractional multiplication where the final result is rounded deterministically using banker's rounding (`ROUND_HALF_EVEN`) to an integer minor unit.

### 6.2 Expected Recovery Value (ERV) Formula
For an opportunity $i$ with transaction amount $A_i$ (in paise):
$$ERV_i = \left\lfloor A_i \times P_{\text{recovery}}(i) \times P_{\text{action\_success}}(a, i) \right\rfloor$$
Where:
- $A_i$: Gross transaction amount in paise.
- $P_{\text{recovery}}(i) \in [0.0, 1.0]$: Base probability that this specific failure condition can ever be recovered.
- $P_{\text{action\_success}}(a, i) \in [0.0, 1.0]$: Probability that the chosen recovery intervention $a \in \{\text{RETRY}, \text{PAYMENT\_LINK}, \text{REMINDER}, \text{STOP}\}$ will succeed.

### 6.3 Deterministic Recoverability Scoring Model
The Recoverability Score $S_i \in [0, 100]$ is computed deterministically from 5 weighted components:
$$S_i = \min\left(100, \max\left(0, \sum_{k=1}^{5} w_k \cdot f_k(i)\right)\right)$$

| Component | Weight $w_k$ | Evaluation Logic |
| :--- | :--- | :--- |
| **Failure Category ($f_1$)** | 35% | Soft decline (e.g., balance, network, bank timeout) = 1.0; 3DS authentication failure = 0.6; Card expired = 0.3; Hard decline (stolen, fraud) = 0.0. |
| **Retry Decay ($f_2$)** | 25% | $\max(0, 1.0 - (\text{retry\_count} \times 0.35))$. Repeated failures rapidly penalize recoverability. |
| **Recency / Age ($f_3$)** | 20% | Exponential decay based on age in hours: $e^{-\lambda \cdot t}$ where half-life is 12 hours. |
| **Customer Prior History ($f_4$)** | 10% | Known successful customer = 1.0; First-time customer = 0.6; High past failure rate = 0.2. |
| **Transaction Size Suitability ($f_5$)** | 10% | Optimal range ₹500–₹25,000 = 1.0; Micro-transactions (<₹100) or massive transactions (>₹1,00,000) = 0.5. |

### 6.4 Priority Rank
Opportunities are ranked by:
$$\text{PriorityRank} = \text{ERV}_i \times \frac{S_i}{100}$$
This ensures the highest absolute recoverable monetary value with the greatest likelihood of success is presented at the top of the operator's queue.

---

## 7. Recovery Brain (AI Engine)

The Recovery Brain is a **single logical advisory engine** powered by the official Google GenAI Python SDK (`google-genai`), using the model specified by `GEMINI_MODEL` (default: `gemini-3.6-flash`).

### 7.1 Input Context
The model is fed only sanitized, bounded domain data:
- Amount and currency (e.g., `499900 INR`)
- Failure reason code & category
- Retry count & max allowed
- Age of payment
- Prior customer transaction count and success rate
- Available recovery channels (`RETRY`, `PAYMENT_LINK`, `REMINDER`, `STOP`)

### 7.2 Strict Bounded Output Schema
The LLM response is parsed and validated using a strict Pydantic model:
```json
{
  "action": "RETRY | PAYMENT_LINK | REMINDER | STOP",
  "confidence": 0.88,
  "expected_recovery_value_paise": 399920,
  "reason": "Clear, concise 1-2 sentence audit explanation.",
  "supporting_factors": [
    "Factor 1",
    "Factor 2"
  ],
  "risk_factors": [
    "Risk 1"
  ]
}
```

### 7.3 Guardrails & Sandbox Isolation
- **No Database Access:** The LLM cannot query or mutate MongoDB.
- **No Network Egress:** The LLM cannot invoke Razorpay or any external HTTP API.
- **Strict Fallback:** If the Gemini API times out, returns malformed JSON, or exceeds rate limits, the engine immediately yields a deterministic, safe fallback decision: `action: STOP` with explanation: `Fallback: AI service unavailable, execution held for manual review.`

---

## 8. Guarded Autopilot (Deterministic Policy Engine)

The policy engine is the **sole authorization gatekeeper**. AI recommendations have zero authority until they receive an `APPROVED` verdict from the policy rules.

```
┌─────────────────────────┐
│ AI Recommendation:     │
│ action = PAYMENT_LINK   │
└────────────┬────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────┐
│             GUARDED AUTOPILOT RULES GATE               │
│                                                        │
│ 1. Payment Eligibility: Is payment status 'failed'?   │
│ 2. Already Recovered: Has payment already succeeded?   │
│ 3. Retry Limit: Is retry_count < max_retries?          │
│ 4. Idempotency Check: Was this exact action already   │
│    executed for this payment in the last 24h?          │
│ 5. Monetary Sanity: Is amount > 0 and <= max limit?   │
│ 6. Customer Suppression: Is customer on do-not-spam?  │
│ 7. Action Supported: Is action in permitted enum?     │
└────────────┬─────────────────────────────┬─────────────┘
             │                             │
    ALL RULES PASS                 ANY RULE FAILS
             │                             │
             ▼                             ▼
   ┌───────────────────┐         ┌───────────────────┐
   │     APPROVED      │         │      BLOCKED      │
   │ Proceed to Razorpay│        │ Halt Execution    │
   │ Adapter Execution │         │ Log Audit Reason  │
   └───────────────────┘         └───────────────────┘
```

---

## 9. Razorpay Integration & Webhook Pipeline

### 9.1 Adapter Architecture
All Razorpay REST API communications are encapsulated inside `RazorpayAdapter`:
- `create_payment_link(payment_id, amount_paise, currency, customer_info)`
- `fetch_payment(payment_id)`
- Handles network timeouts, exponential retry on 5xx, structured error translation.
- **Zero secret logging:** `RAZORPAY_KEY_SECRET` and authorization headers are scrubbed from all logging handlers.

### 9.2 Cryptographic Webhook Ingestion
Webhooks are received over HTTPS:
1. Extract signature from `X-Razorpay-Signature`.
2. Compute HMAC-SHA256 of raw request body using `RAZORPAY_WEBHOOK_SECRET`.
3. Compare signatures using constant-time string comparison (`hmac.compare_digest`).
4. Reject with HTTP 400 if invalid.
5. Check `webhook_events` collection by `event_id` for idempotency. If already processed, return HTTP 200 immediately.
6. Persist event, update `payments` and `recovery_actions` state.
7. Broadcast real-time `payment.updated` and `metrics.updated` event to connected WebSocket clients.

---

## 10. Outcome Measurement & Incremental Lift

### 10.1 Control vs RevenueOS Methodology
To measure true recovery performance without faking numbers:
- **Baseline Group (Control):** Represents standard merchant behavior (either no recovery or single unguided automated retry). Documented heuristic baseline recovery rate $R_{\text{baseline}} \approx 12\%$.
- **RevenueOS Group:** Actual measured recoveries executed through RevenueOS interventions.
- **Incremental Revenue:**
$$\text{Incremental Revenue} = \text{Recovered Revenue}_{\text{RevenueOS}} - \left( \text{Revenue at Risk} \times R_{\text{baseline}} \right)$$

If no actual transaction outcomes have been recorded, the UI displays an explicit empty state:
*"No recovery outcomes recorded yet. Connect payment data or trigger test opportunities to evaluate recovery performance."*

---

## 11. Security Model

1. **Authentication:** Argon2id password hashing ($m=65536, t=3, p=4$).
2. **Bot Prevention:** Cloudflare Turnstile verification required on login. The client receives a Turnstile token which the backend verifies directly with `https://challenges.cloudflare.com/turnstile/v0/siteverify`.
3. **Session Cookies:** `HttpOnly`, `SameSite=Lax` (or `None` in cross-origin production with `Secure=True`), `Secure=True` in production.
4. **WebSocket Security:** Handshake validates session cookie. Unauthenticated connections are closed immediately with code `4401 (Unauthorized)`.
5. **Origin Verification:** Both HTTP and WebSocket connections validate incoming `Origin` against `DJANGO_ALLOWED_HOSTS` and `FRONTEND_ORIGIN`.

---

## 12. Deployment Topology

```
                  ┌───────────────────────────────┐
                  │       Vercel Platform         │
                  │   (Next.js App Router Frontend│
                  │        Static Assets & SSR)   │
                  └───────────────┬───────────────┘
                                  │
                          HTTPS / WSS (TLS)
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │       Render Platform         │
                  │  (Django + Channels + Uvicorn │
                  │     Listening on 0.0.0.0:PORT)│
                  └───────┬───────────────┬───────┘
                          │               │
                 TLS Mongo Connection   HTTPS
                          │               │
                          ▼               ▼
                  ┌──────────────┐  ┌─────────────┐
                  │MongoDB Atlas │  │Razorpay /   │
                  │  (Free Tier) │  │Gemini APIs  │
                  └──────────────┘  └─────────────┘
```

---
*RevenueOS Architecture Specification — Approved for Phase 0 Implementation.*
