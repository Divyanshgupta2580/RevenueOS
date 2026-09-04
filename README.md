# RevenueOS — AI Revenue Recovery Decision Engine

**Target Track**: Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery  
**Category**: Fintech Decision Engine & Guarded Autopilot Pipeline  
**Architecture**: Modular Monolith &bull; WebSocket-First &bull; Deterministic Policy Guarded &bull; Zero Dummy Data  

---

## 1. What RevenueOS Is

RevenueOS is an AI Revenue Recovery Decision Engine designed to solve a critical fintech problem:
**When digital commerce payments fail, which transactions should merchants recover first, what is the safest and highest-value intervention, and how much incremental revenue did the system actually recover?**

RevenueOS bridges the gap between probabilistic AI reasoning and deterministic financial safety. It uses **Google Gemini 3.6 Flash** (strictly governed via the centralized configuration key `GEMINI_MODEL=gemini-3.6-flash`) as an isolated advisory engine, gated behind an auditable, deterministic **Guarded Autopilot Policy Engine** that executes bounded recovery workflows via **Razorpay Test Mode APIs, Simulated Test Actions, and HMAC-SHA256 Signed Webhooks**.

---

## 2. Problem Statement & Why Revenue Recovery Matters

### The Core Problem
Failed payments in digital commerce are not uniform:
1. **Naive Retries Cause Churn & Waste Fees**: Unconditionally retrying hard declines (e.g., stolen cards, closed accounts) wastes gateway retry fees and annoys customers.
2. **Untracked High-Value Opportunities**: High-value transactions with transient soft declines (e.g., temporary network timeouts, low balance) are frequently abandoned without proactive customer outreach.
3. **Black-Box AI Danger**: Autonomous LLMs cannot be given direct access to mutate financial balances or execute banking transactions without deterministic guardrails.
4. **Unmeasured Value Claims**: Most recovery systems claim arbitrary percentage lifts without comparing outcomes against an unguided baseline control.

### The RevenueOS Solution
RevenueOS answers three questions deterministically:
1. **Which revenue at risk should be recovered first?** (Deterministic ERV & Recoverability Score).
2. **What is the safest and highest-value recovery action?** (Gemini 3.6 Flash recommendations gated by Guarded Autopilot rules).
3. **How much incremental revenue was actually recovered?** (Transparent comparison of Baseline Assumption vs Observed Recovery vs AI Lift).

---

## 3. High-Level Architecture

RevenueOS is engineered as a lean, explainable, modular monolith.

```
Browser (Operator Client)
    |
    +---- HTTPS: Next.js Frontend (Vercel)
    |
    +---- WSS:   Django Channels WebSocket (Render / Daphne ASGI)
    |
    v
RevenueOS Backend (Django Channels + Daphne ASGI)
    |
    +---- PyMongo (Direct Driver) -------> MongoDB Atlas Free Tier (Persistent Collections)
    |
    +---- Google GenAI SDK (Isolated) ---> Google Gemini 3.6 Flash (GEMINI_MODEL)
    |
    +---- REST HTTPS Adapter -----------> Razorpay Test Mode API
    |
    <---- HMAC-SHA256 Webhooks <--------- Inbound Razorpay Events (/api/webhooks/razorpay/)
```

### Technology Stack
- **Backend**: Django 5 + Django Channels 4 running on Daphne / Uvicorn ASGI.
- **Database**: MongoDB Atlas M0 Free Tier via PyMongo (zero ORM overhead, flexible schema).
- **AI Core**: Official `google-genai` SDK targeting **Gemini 3.6 Flash** via centralized configuration.
- **Frontend**: Next.js 16 (App Router) + Tailwind CSS + Lucide Icons (zero emojis, fintech typography).
- **Realtime**: WebSocket RPC & Event Streaming over `/ws/v1/app/` with heartbeat and reconnection.
- **Payments**: Razorpay Standard Web Checkout modal with server-side order creation and HMAC-SHA256 signature verification.
- **Security**: Cloudflare Turnstile CAPTCHA verification, Argon2id password hashing, constant-time HMAC validation.

---

## 4. Single Gemini Model Source of Truth (`gemini-3.6-flash`)

RevenueOS enforces strict Gemini model governance:
- **Central Configuration**: `GEMINI_MODEL=gemini-3.6-flash` is loaded from the environment through `apps.brain.config.RecoveryBrainConfig`.
- **Application Governance**: `APPROVED_GEMINI_MODEL = "gemini-3.6-flash"`. The environment value selects the model, and the application governance constant validates that only the approved model may execute.
- **Zero Model Drift**: Any runtime attempt to use missing, empty, or unapproved model identifiers fails immediately with a `ValueError`.
- **Automated Governance Scanner**: An automated test (`backend/tests/test_gemini_model_governance.py`) continuously validates that configuration and repository files strictly adhere to `gemini-3.6-flash`.

---

## 5. AI Decision Context Engine

RevenueOS implements an isolated, high-signal **AI Decision Context Engine** that orchestrates Google Gemini as a bounded advisory system while preserving strict financial determinism.

```
       Payment Facts + Backend Math + Policy Rules
                           │
                           ▼
              DecisionContextEnvelope (v1.0)
                           │
                           ▼
          Google Gemini 3.6 Flash (Reasoning)
                           │
                           ▼
             Strict Pydantic JSON Output
                           │
                           ▼
          Guarded Autopilot Deterministic Engine
                     ┌─────┴─────┐
                     ▼           ▼
                 APPROVED     BLOCKED
```

### 1. Why RevenueOS Uses Gemini
Failed digital payment recovery is fundamentally multi-dimensional: decline codes alone (`gateway_error`, `soft_decline`) do not explain customer context, recency, or channel preference. Gemini 3.6 Flash provides low-latency, nuanced contextual reasoning to choose between bounded recovery strategies (`PAYMENT_LINK`, `REMINDER`, `RETRY`, `STOP`), weighing customer history and transient failure descriptions without hallucinating or taking unconstrained actions.

### 2. Why Gemini Does Not Perform Financial Arithmetic
LLMs are probabilistic and susceptible to numerical drift. RevenueOS **never** delegates financial arithmetic to Gemini:
- **Zero Floating-Point Money**: All financial calculations operate on authoritative integer minor units (paise).
- **Authoritative Calculations**: Expected Recovery Value (ERV), Recoverability Scores (0–100), Baseline Controls (8% heuristic assumption), and Estimated Lift are pre-calculated deterministically by backend algorithms before any AI prompt is assembled.
- Gemini receives pre-calculated numbers as read-only verified context and is prohibited from altering amounts.

### 3. How Endpoint-Specific Context is Built
RevenueOS strictly avoids dumping generic unstructured blobs into AI prompts. Each AI task uses an endpoint-specific **DecisionContextEnvelope (Protocol v1.0)**:
- **`recovery.analyze`**: Ingests payment facts, failure taxonomy, retry counts, recoverability score, and allowed action spaces to output the optimal recovery strategy.
- **`decision.explain`**: Ingests the recorded audit decision, policy rules evaluated, blocking rationale (if any), and execution results to produce a transparent explanation for merchant operators without mutating state.

Every context field is classified into one of six audit tiers:
- `VERIFIED_FACT`: Incontestable payment state (e.g., paymentId, amountPaise, currency, status, gateway failure code).
- `BACKEND_CALCULATION`: Deterministic arithmetic (e.g., ageHours, recoverabilityScore, ERV, baselineControl).
- `HISTORICAL_EVIDENCE`: Bounded customer history (e.g., success/failure aggregates, previous recovery actions count).
- `POLICY`: Non-negotiable merchant constraints (e.g., maxRetries, cooldownSeconds, allowedActions).
- `SYSTEM_STATE`: Runtime capabilities and execution eligibility (e.g., simulatedRetryAvailable, isTestMode).
- `AI_TASK_METADATA`: Protocol version, task identifier, requestId, and timestamp.

### 4. How the Model is Governed
Model governance enforces a single approved model across the entire application lifecycle:
- **Environment**: `GEMINI_MODEL=gemini-3.6-flash` selects the requested runtime model.
- **Application Governance**: `APPROVED_GEMINI_MODEL = "gemini-3.6-flash"` in `apps.brain.config` validates that only the approved model may execute.
- **Drift Protection**: If `GEMINI_MODEL` is missing, empty, or set to an unapproved model, the application fails safely and immediately with a `ValueError`.
- An automated repository scan test (`test_no_forbidden_models_in_codebase`) continuously verifies zero unauthorized model strings exist in the codebase.

### 5. How Structured Output is Validated
Gemini output is constrained via `response_mime_type="application/json"` and validated against strict Pydantic schemas (`RecoveryBrainOutput` and `DecisionExplanationOutput`):
- Action must strictly be one of `["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"]`.
- Confidence is validated within `[0.0, 1.0]`.
- Expected Recovery Value is enforced as a non-negative integer.
- Markdown code fence wrapping is automatically stripped and malformed payloads trigger graceful fallback handling.

### 6. How Policy Guards AI Recommendations
Gemini acts solely as an advisory engine—it possesses **zero direct mutation capability**. Every recommendation is passed to **Guarded Autopilot**, a deterministic policy engine that enforces:
- Hard stop on terminal failure categories (fraud, stolen cards, closed accounts).
- Strict enforcement of the 3-attempt retry ceiling.
- Minimum 300-second cooldown windows between retry actions.
- Verification that the payment has not already been settled or captured.

### 7. How AI Failures Fall Back Safely
If Gemini encounters network timeouts, HTTP 503 high-demand spikes, rate limits, or invalid JSON, RevenueOS guarantees zero downtime and zero unsafe actions:
- Caught exceptions immediately engage the deterministic fallback heuristic engine.
- Fallback recommendations match Radar deterministic scoring rules (`soft_decline` $\rightarrow$ `PAYMENT_LINK`, transient errors $\rightarrow$ `RETRY` if cooldown elapsed, fraud $\rightarrow$ `STOP`).
- Fallback status is recorded explicitly (`fallback_used: YES` / `is_fallback: True`) for complete operational transparency.

### 8. How Decisions Become Auditable
Every AI evaluation is committed to an immutable MongoDB **Decision Ledger**:
- Records: Decision ID, timestamp, paymentId, model version (`gemini-3.6-flash`), action, confidence, ERV, reason, policy verdict (`APPROVED` / `BLOCKED`), evaluated rules, and execution outcomes.
- Provides complete auditability for financial operators and regulators.

---

## 6. The Core Product Loop

```
REAL PAYMENT DATA (Razorpay / MongoDB)
      ↓
REVENUE RADAR (At-Risk Identification & Ranking)
      ↓
DETERMINISTIC RECOVERABILITY SCORE & ERV (Integer Minor Units)
      ↓
ENDPOINT-SPECIFIC DECISION CONTEXT ENVELOPE (Protocol v1.0)
      ↓
GEMINI 3.6 FLASH (Reasoning & Structured Recommendation)
      ↓
SCHEMA VALIDATION (Bounds, Confidences, Integer Paise)
      ↓
GUARDED AUTOPILOT (Deterministic Policy Engine)
      ↓
APPROVED / BLOCKED
      ↓
BOUNDED RECOVERY ACTION (Razorpay API / Simulated Action)
      ↓
IMMUTABLE AUDIT TRAIL (Decision Ledger + AI Explainability)
      ↓
MEASURED OUTCOME (Outcome Metrics & Incremental Lift)
```

---

## 7. The 5 Core Product Modules

### A. Revenue Radar
- Identifies failed transactions in real time from MongoDB Atlas.
- Calculates **Recoverability Score** ($S_i \in [0, 100]$):
  - Category multiplier: network timeout (1.0), gateway error (0.95), soft decline (0.75), insufficient funds (0.70), hard decline (0.05), fraud (0.00).
  - Retry decay multiplier: $1 - \frac{\text{retries}}{\text{maxRetries}}$.
  - Age decay multiplier: degrades over 0.5h, 3h, 12h, 48h, 5d.
- Computes **Expected Recovery Value (ERV)** in integer paise:
  $$\text{ERV} = \text{floor}(\text{AmountPaise} \times \frac{\text{Score}}{100} \times P(\text{Action}))$$
- Privacy-safe masked customer display (`op***@revenueos.local` or `cust_***123`).

### B. Recovery Brain
- Evaluates the bounded recovery intervention:
  - `PAYMENT_LINK`: Generates personalized payment links via Razorpay API.
  - `REMINDER`: Triggers scheduled notifications via Razorpay.
  - `RETRY`: Algorithmic retry benchmarking (clearly labeled as a **Simulated Test Action**).
  - `STOP`: Policy termination for unrecoverable declines.
- Strict fallback: If the Gemini API is unreachable, rate-limited, or returns invalid JSON, the system safely falls back to a deterministic heuristic recommendation.

### C. Guarded Autopilot
Every AI recommendation passes through 8 deterministic policy checks before execution:
1. `USER_AUTHORIZATION`: Operator session has financial action rights.
2. `SUPPORTED_ACTION`: Action is in {`RETRY`, `PAYMENT_LINK`, `REMINDER`, `STOP`}.
3. `PAYMENT_ELIGIBILITY`: Payment is currently in `failed` status.
4. `ALREADY_RECOVERED`: Transaction not already settled or captured.
5. `AMOUNT_VALIDITY`: Amount is a positive integer minor unit (paise $\ge 100$).
6. `RETRY_THRESHOLD`: Retries remain strictly below policy ceiling (default: 3).
7. `RISK_POLICY`: Blocked on stolen cards, fraud, or blacklisted accounts.
8. `DUPLICATE_EXECUTION`: In-flight idempotency guards prevent double executions.

### D. Decision Ledger & AI Explainability
- Immutable audit timeline recording:
  - Timestamp, Decision ID, Payment ID, AI Recommendation, Model Version (`gemini-3.6-flash`), Confidence, Policy Result (`APPROVED` / `BLOCKED`), Reason / Rule.
- Click any decision row to open the **Decision Audit Modal**.
- **Deep Explain (Gemini 3.6 Flash)**: Calls `decision.explain` RPC to generate structured post-decision explanations breaking down factual evidence, policy alignment, and counterfactuals.

### E. Outcome Metrics
- Sourced exclusively from genuine MongoDB transactions:
  - **Revenue at Risk**: Total unsettled failed volume.
  - **Expected Recoverable**: Sum of deterministic ERVs.
  - **Actually Recovered**: Verified webhook captures.
  - **Estimated Lift**: Recovery above the 8% baseline assumption.
  - **Recovery Rate**: Total conversion efficiency.
- **Strategy Breakdown**: Honest reporting across `PAYMENT_LINK`, `REMINDER`, `RETRY`, and `STOP` with sample size disclosures.
- **Truthful Empty States**: If no failed payments exist, shows honest empty states—no fabricated charts or synthetic data.

---

## 8. Razorpay Standard Web Checkout

- Integrated with **Razorpay Standard Web Checkout** (`checkout.js`).
- Complete verified pipeline:
  1. Backend `POST /api/create-order` creates secure Razorpay order.
  2. Frontend opens standard modal with `key_id`, `order_id`, and test customer data.
  3. Upon payment, frontend sends `razorpay_payment_id`, `razorpay_order_id`, and `razorpay_signature` to `POST /api/verify-payment`.
  4. Backend verifies HMAC-SHA256 signature using `RAZORPAY_KEY_SECRET` and records the transaction in MongoDB.
  5. UI displays verified receipt details, copyable IDs, and `Make Another Payment` CTA.

---

## 9. Security & Privacy Model

- **Zero Secrets in Frontend**: `RAZORPAY_KEY_SECRET`, `GEMINI_API_KEY`, `MONGODB_URI`, `DJANGO_SECRET_KEY`, and `TURNSTILE_SECRET_KEY` are never bundled into client JS.
- **Integer Minor Units**: All monetary values are processed and stored as integer paise (minor units) to eliminate IEEE 754 floating-point errors.
- **PII Minimization**: No raw credit card numbers, CVVs, or unmasked credentials are ever sent to Gemini or stored.
- **Cloudflare Turnstile**: Mandatory cryptographic verification on authentication endpoints.
- **Anti-Hijacking**: WebSocket connections validate `Origin` against allowed origins.

---

## 10. Local Development Setup

### Prerequisites
- Python 3.12+ (or 3.14)
- Node.js 20+
- MongoDB instance (MongoDB Atlas URI or local MongoDB)

### Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# Fill in your MONGODB_URI, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, GEMINI_API_KEY, and TURNSTILE keys
python manage.py runserver 0.0.0.0:8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## 11. Test Suite Verification

RevenueOS includes comprehensive automated test suites:

### Backend Tests (Pytest, Ruff, Mypy)
```bash
# Run 121 comprehensive tests
backend/.venv/bin/pytest backend/tests/

# Static analysis and linting
backend/.venv/bin/ruff check backend/
backend/.venv/bin/mypy --ignore-missing-imports backend/apps/
```
- **121 / 121 Passed** in 2.6s.
- **0 Ruff errors**.
- **0 Mypy issues** across 50 source files.

### Frontend Quality & Production Build
```bash
cd frontend
npm run lint
npm run build
```
- **0 ESLint errors or warnings**.
- **Production Webpack bundle compiled cleanly**.

### Playwright End-to-End Suite
```bash
cd frontend
npx playwright test
```
- **10 / 10 Tests Passed** in 4.5s covering authentication, KPI cards, tab switching, truthful empty states, zero emojis, checkout UI, and WebSocket connectivity.

---

## 12. Deployment Topology

- **Frontend**: Next.js App Router configured for **Vercel** (`frontend/vercel.json`).
- **Backend**: Django Channels ASGI web service configured for **Render** (`render.yaml`) running on Daphne / Uvicorn.
- **Database**: **MongoDB Atlas** M0 cluster configured via `MONGODB_URI` and `MONGODB_DB`.

---

## 13. Limitations & Future Improvements

1. **Direct Card Re-charging**: Standard one-time web checkouts require customer 3D-Secure re-authentication. Direct server-to-server retries without customer interaction are designated as a **Simulated Test Action** for algorithmic benchmarking.
2. **Attribution Sample Size**: Meaningful statistical significance for multi-channel strategy attribution requires 250+ completed transactions per channel. Low sample sizes are explicitly disclosed in the UI.
3. **Future Work**: Adding automated WhatsApp notification channels for payment recovery links and integration with recurring card tokenization.
