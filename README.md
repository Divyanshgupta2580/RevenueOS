# RevenueOS — AI Revenue Recovery Decision Engine

> **Razorpay AI Buildathon 2026** — *Track 03: AI Revenue Recovery*

RevenueOS is an autonomous, production-grade decision engine that identifies at-risk revenue, ranks opportunities deterministically, recommends bounded recovery actions via Google Gemini, gates every action through a deterministic safety policy engine, executes approved actions through Razorpay Test APIs, and measures actual incremental recovery against a strict baseline.

---

## 1. The Core Product Question

> *"Which revenue at risk should be recovered first, what is the safest and highest-value recovery action, and how much incremental revenue did RevenueOS actually recover?"*

Most failed payment retry mechanisms operate naively: they either blindly retry cards (triggering scheme fees and high decline ratios) or abandon soft-declined transactions entirely. RevenueOS solves this with four core pillars:

1. **IDENTIFY:** Pinpoint transactions genuinely at risk using deterministic categorization (soft declines, authentication drops, balance limits) versus fatal hard declines.
2. **PRIORITIZE (Revenue Radar):** Calculate deterministic **Recoverability Scores** and **Expected Recovery Values (ERV)** in integer minor units (paise) to rank the most lucrative, savable capital first.
3. **DECIDE (Recovery Brain):** A single logical AI decision engine using Google Gemini that outputs bounded, schema-validated actions (`RETRY`, `PAYMENT_LINK`, `REMINDER`, `STOP`) with an audit-ready reasoning trail.
4. **EXECUTE & MEASURE (Guarded Autopilot):** Zero unverified AI execution. All recommendations pass through a deterministic policy gate enforcing retry ceilings, idempotency, customer fatigue suppression, and status validity. Measures real incremental recovery ($Y - X$) against empirical control benchmarks.

---

## 2. System Architecture

RevenueOS is architected as a lean, secure, modular monolith:

- **Frontend:** Next.js 15 (App Router), TypeScript, Tailwind CSS, Lucide React. High-density dark fintech theme.
- **Backend:** Python 3.14, Django 5+, Django Channels, Uvicorn ASGI.
- **Database:** MongoDB Atlas Free Tier via PyMongo directly (zero ORM overhead).
- **Real-Time Layer:** WebSocket-first protocol (`/ws/v1/app/`) with heartbeats, correlation IDs, and resilient reconnection.
- **Security:** Cloudflare Turnstile anti-bot verification, Argon2id password hashing, HTTP-only session cookies.
- **Zero Dummy Data:** Strict policy against fabricated metrics or placeholder transactions.

```
Browser (Next.js Dark Dashboard)
       │ (WSS Application RPC / HTTPS Auth)
       ▼
Render Web Service (Django Channels + Uvicorn ASGI)
       ├── PyMongo ──────────► MongoDB Atlas Free Tier
       ├── GenAI SDK ────────► Google Gemini API (Recovery Brain)
       ├── Policy Gate ──────► Guarded Autopilot (Rules Engine)
       ├── Razorpay REST ────► Razorpay Test Platform
       └── HTTPS Webhooks ───◄ Razorpay Webhook Ingestion (HMAC-SHA256)
```

---

## 3. Documentation Index

- [System Architecture (ARCHITECTURE.md)](docs/ARCHITECTURE.md): Full technical breakdown, data models, ERV formulas, and component architecture.
- [WebSocket Protocol v1 (WEBSOCKET_PROTOCOL.md)](docs/WEBSOCKET_PROTOCOL.md): Envelope structure, message catalog, heartbeat, and reconnection lifecycles.
- [Deployment Runbook (DEPLOYMENT.md)](docs/DEPLOYMENT.md): Production deployment guides for Vercel, Render, and MongoDB Atlas.
- [Canonical Configuration (.env.example)](.env.example): Environment variable templates.

---

## 4. Free-Tier Operating Constraints

RevenueOS is engineered to run permanently on free infrastructure:
- **MongoDB Atlas:** Free M0 cluster (512 MB). Bounded reads, projections, and minimal indexing ensure low memory usage.
- **Render:** Free Web Service with ASGI Uvicorn single-worker process.
- **Vercel:** Hobby tier for Next.js SSR and static asset CDN.
- **Razorpay:** Sandbox Test Mode credentials with zero transaction processing fees.
- **Google Gemini:** Free tier API quota with rate-limited bounded calls.
- **Cloudflare Turnstile:** Free tier anti-bot challenge validation.

---

## 5. Development Roadmap & Phased Execution

- [x] **Phase 0:** Inspection and Architecture Specification (Completed)
- [ ] **Phase 1:** Project Skeleton & Tooling (Next.js, Django, Channels, PyMongo, Linters)
- [ ] **Phase 2:** Authentication & Cloudflare Turnstile Security
- [ ] **Phase 3:** Real-Time WebSocket Infrastructure & Protocol Audit
- [ ] **Phase 4:** MongoDB Atlas PyMongo Persistence Layer
- [ ] **Phase 5:** Revenue Radar & Deterministic ERV Math
- [ ] **Phase 6:** Recovery Brain AI Engine (Gemini SDK Integration)
- [ ] **Phase 7:** Guarded Autopilot Deterministic Policy Engine
- [ ] **Phase 8:** Razorpay Test API Client Adapter
- [ ] **Phase 9:** Signed Webhook Ingestion Pipeline
- [ ] **Phase 10:** High-Density Dark Fintech Frontend
- [ ] **Phase 11:** End-to-End Recovery Pipeline Integration
- [ ] **Phase 12:** Quality, Security, and Playwright Testing Audit
- [ ] **Phase 13:** Vercel & Render Deployment Verification
- [ ] **Phase 14:** Production WebSocket Resilience Audit
- [ ] **Phase 15:** Final Repository & Zero-Emoji Code Audit

---
*RevenueOS — Built for the Razorpay AI Buildathon 2026.*
