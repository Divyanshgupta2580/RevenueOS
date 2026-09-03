# RevenueOS — AI Revenue Recovery Decision Engine

**Target Track**: Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery  
**Category**: Fintech Decision Engine & Guarded Autopilot Pipeline  
**Architecture**: Modular Monolith &bull; WebSocket-First &bull; Deterministic Policy Guarded  

---

## 1. What RevenueOS Is

RevenueOS is an AI Revenue Recovery Decision Engine designed to solve a critical fintech problem:
When online payments fail, which transactions should merchants recover first, what is the safest and highest-value intervention, and how much incremental revenue did the system actually recover?

RevenueOS bridges the gap between probabilistic AI reasoning and deterministic financial safety. It uses **Google Gemini 2.0 Flash** (configurable via `GEMINI_MODEL`) as an isolated advisory engine, gated behind an auditable, deterministic **Guarded Autopilot Policy Engine** that executes bounded recovery workflows via **Razorpay Test Mode APIs, Simulated Test Actions, and Signed Webhooks**.

---

## 2. Problem Statement & Why It Matters

### The Core Problem
Failed payments in digital commerce are not uniform:
1. **Naive Retries Cause Churn**: Unconditionally retrying hard declines (e.g. stolen card, expired card) wastes gateway retry fees and damages merchant reputation.
2. **Untracked Opportunities**: High-value transactions with transient soft declines (e.g. temporary network timeouts, low balance) are frequently abandoned without proactive customer outreach.
3. **Black-Box AI Danger**: Autonomous LLMs cannot be given direct access to mutate financial balances or execute banking transactions without deterministic guardrails.
4. **Unmeasured Value**: Most recovery systems claim arbitrary percentage lifts without comparing outcomes against an unguided baseline control.

### The RevenueOS Solution
RevenueOS answers three questions deterministically:
1. **Which revenue at risk should be recovered first?** (Deterministic ERV & Recoverability Score).
2. **What is the safest and highest-value recovery action?** (Gemini recommendations gated by Guarded Autopilot rules).
3. **How much incremental revenue was actually recovered?** (Transparent comparison of Baseline Assumption vs Observed Recovery).

---

## 3. High-Level Architecture & Technology Choices

RevenueOS is engineered as a lean, explainable, modular monolith.

```
Browser (Operator Client)
    |
    +---- HTTPS: Next.js Frontend (Vercel)
    |
    +---- WSS:   Django Channels WebSocket (Render)
    |
    v
RevenueOS Backend (Django Channels + Uvicorn)
    |
    +---- PyMongo (Direct Driver) -------> MongoDB Atlas Free Tier (Persistent Collections)
    |
    +---- Google GenAI SDK (Isolated) ---> Google Gemini API (GEMINI_MODEL)
    |
    +---- REST HTTPS Adapter -----------> Razorpay Test Mode API
    |
    <---- HMAC-SHA256 Webhooks <--------- Inbound Razorpay Events (/api/webhooks/razorpay/)
```

### Why These Technology Choices?
- **Why Django + Channels + Uvicorn?**  
  Django provides robust security primitives, CSRF protection, secure HTTP-only session cookies, and clean ASGI concurrency through Channels and Uvicorn. It avoids microservice proliferation while offering an enterprise-grade modular structure.
- **Why WebSockets-First?**  
  Fintech operators need real-time radar scanning, instant AI analysis streaming, and immediate webhook state synchronization without inefficient polling loops.
- **Why MongoDB via Direct PyMongo?**  
  Payment metadata, failure context, and audit trails possess varied schema attributes depending on payment method (cards, UPI, netbanking). PyMongo delivers zero-overhead, schema-flexible persistence without heavy, unnecessary ORM abstractions.
- **Why No Redis / Celery / Kafka?**  
  To strictly maintain the free-tier constraint and keep deployment transparent, operations run efficiently within an in-memory asynchronous event loop with idempotent database state persistence.

---

## 4. The 4 Core Product Pillars

### A. Revenue Radar (Deterministic Prioritization)
- Scans failed payments and computes:
  - **Recoverability Score** ($S_i \in [0, 100]$): Derived deterministically from payment age decay, failure category weights (soft vs hard decline), and retry history multiplier ($0.95^{\text{retries}}$).
  - **Expected Recovery Value (Paise)**:
    $$\text{ERV} = \text{Amount} \times P(\text{Recovery}) \times P(\text{Action Success})$$
  - Strictly operates on **integer minor currency units (paise)**. Floating-point arithmetic on currency is strictly forbidden.

### B. Recovery Brain (Gemini AI Advisory)
- Single logical decision engine powered by the official `google-genai` SDK using `GEMINI_MODEL` (default: `gemini-2.0-flash`).
- Constrained to a bounded decision space:
  - `PAYMENT_LINK`: Issue dynamic Razorpay payment link for customer checkout completion (backed by Razorpay Test Mode API `POST /v1/payment_links`).
  - `REMINDER`: Dispatch non-intrusive reminder for pending authorization (backed by Razorpay API `POST /v1/payment_links/:id/notify_by/:medium`).
  - `RETRY`: Direct automated retry evaluation. Note: Standard one-time checkout payments require customer 3D-Secure re-authentication. Direct server-to-server retries without customer involvement are designated as a **Simulated Test Action** for algorithmic benchmarking.
  - `STOP`: Deliberate termination of recovery attempts for fraud or hard declines (internal terminal policy action).
- **Strict Isolation**: The model receives structured context only; it has zero direct database or payment API access and cannot mutate records.

### C. Guarded Autopilot (Deterministic Policy Engine)
Every AI recommendation is validated by 8 deterministic rules before execution:
1. `USER_AUTHORIZATION`: Verify operator has permission to trigger financial actions.
2. `SUPPORTED_ACTION`: Enforce action is in {`RETRY`, `PAYMENT_LINK`, `REMINDER`, `STOP`}.
3. `PAYMENT_ELIGIBILITY`: Payment must exist and be in `failed` status.
4. `ALREADY_RECOVERED`: Reject execution on previously captured transactions.
5. `AMOUNT_VALIDITY`: Validate amount is a positive integer minor unit.
6. `RETRY_THRESHOLD`: Block retries exceeding maximum configured threshold.
7. `RISK_POLICY`: Block attempts on fraud, stolen cards, or blacklisted accounts.
8. `DUPLICATE_EXECUTION`: Enforce idempotency across session and database keys.

> **Cardinal Rule**: AI recommends. Rules authorize. Only `APPROVED` actions execute.

### D. Outcome Measurement (Incremental Value Lift)
- Tracks financial results populated exclusively from verified webhook captures:
  - **Revenue at Risk**: Total unsettled failed volume.
  - **Observed / Test-Mode Recovery ($Y$)**: Verified captured recovery volume in test mode.
  - **Baseline Assumption ($X$)**: Theoretical unguided retry benchmark (8% heuristic evaluation model; not empirical historical merchant data).
  - **Estimated Incremental Lift**: $Y - X$ relative to baseline assumption.
  - **Production Merchant Recovery**: Explicitly labeled **Not measured** until live merchant production traffic is connected.

---

## 5. Security & Bot Protection

- **Cloudflare Turnstile**: Mandatory anti-bot challenge on login, cryptographically verified server-side.
- **Argon2id Password Hashing**: State-of-the-art memory-hard password derivation via `argon2-cffi`.
- **HMAC-SHA256 Webhook Verification**: Constant-time signature comparison on `X-Razorpay-Signature`.
- **Origin Validation**: WebSocket connections in production validate browser origin against `WS_ALLOWED_ORIGINS` to prevent Cross-Site WebSocket Hijacking (CSWSH).
- **Leaky Bucket Rate Limiting**: Sensitive financial executions are bounded per operator session.
- **Zero Secrets in Code**: 100% environment-driven configuration.

---

## 6. Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- MongoDB instance (local or MongoDB Atlas connection URI)

### Backend Setup
```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp ../.env.example .env
# Edit .env with your credentials

# 5. Run backend server
python -m uvicorn revenueos.asgi:application --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup
```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies
npm install

# 3. Run development server
npm run dev
# Dashboard available at http://localhost:3000
```

---

## 7. Testing & Quality Assurance

### A. Backend Unit, Protocol, and Integration Tests
```bash
backend/.venv/bin/ruff check backend/
PYTHONPATH=backend backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/apps backend/revenueos
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/
```
- **Backend Tests**: 82/82 tests passing in 1.01s (Authentication, WebSocket protocol, PyMongo data layer, Radar scoring, Recovery Brain, Policy engine, Razorpay adapter, Webhooks, Money safety, and Full pipeline).
- **Static Analysis**: Ruff 100% clean, Mypy 100% clean across 53 source files.

### B. Frontend Type Checking & Production Build
```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```
- **TypeScript & Linting**: 0 errors, 0 warnings.
- **Next.js Webpack Build**: Production bundle compiled in 927ms.

### C. Playwright End-to-End Test Suite
```bash
cd frontend
npx playwright test
```
- **E2E Tests**: 7/7 passing in 2.0s covering unauthenticated redirect, Turnstile login validation, Command Center KPI cards, tab navigation, truthful empty states, and zero emojis.

---

## 8. Deployment Status & Topology

- **Deployment Status**:
  - **Deployment Configuration Verified**: Render ASGI blueprint (`render.yaml`), Vercel manifest (`frontend/vercel.json`), database-aware readiness probe (`/ready/`), and production security headers are verified.
  - **Live Cloud Deployment**: Pending provisioning of live production merchant accounts and custom domain records.
- **Topology**:
  - **Frontend**: Designed for **Vercel** with Next.js App Router and strict security headers.
  - **Backend**: Designed for **Render** Web Service using Uvicorn ASGI server with `/health/` and `/ready/` probes.
  - **Database**: Hosted on **MongoDB Atlas** Free Tier (M0).
- Detailed deployment steps are documented in [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 9. Assumptions, Truthful Distinctions & Limitations

1. **Baseline Evaluation Model**: The 8% baseline recovery assumption is a theoretical heuristic model for evaluation comparison, not empirical historical merchant data.
2. **Action Classification**:
   - `PAYMENT_LINK`: Real Razorpay Test Mode API call (`POST /v1/payment_links`).
   - `REMINDER`: Real Razorpay Test Mode API call (`POST /v1/payment_links/:id/notify_by/:medium`).
   - `RETRY`: Simulated Test Action (standard checkouts require customer interaction; direct re-charging is simulated for algorithmic benchmarking).
   - `STOP`: Internal terminal policy action.
3. **Synthetic Test Fixtures**: Transactions in integration tests are synthetic test fixtures strictly isolated in in-memory test databases and never pollute production tables.
4. **Live Production Volume**: Production merchant recovery volume is explicitly marked **Not measured** until live merchant production traffic is connected.
