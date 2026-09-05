# RevenueOS — Deployment Architecture & Runbook

This guide details the production deployment topology, environment configuration, and verification steps for RevenueOS across **Vercel** (Frontend), **Render** (Backend), and **MongoDB Atlas** (Database).

---

## 1. Production Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │             User Browser               │
                      └──────────────────┬─────────────────────┘
                                         │
                         ┌───────────────┴───────────────┐
                         │ HTTPS                         │ WSS
                         ▼                               ▼
      ┌────────────────────────────────────┐   ┌────────────────────────────────────┐
      │          Vercel Platform           │   │          Render Platform           │
      │         (Next.js Frontend)         │   │     (Django Channels ASGI Service) │
      │                                    │   │                                    │
      │ • Edge CDN & SSR                   │   │ • Uvicorn ASGI server              │
      │ • Turnstile Client Widget          │   │ • Listens on 0.0.0.0:$PORT         │
      │ • Secure Cookie Transport          │   │ • WebSockets & Webhooks & Health   │
      └────────────────────────────────────┘   └─────────────────┬──────────────────┘
                                                                 │
                                         ┌───────────────────────┼───────────────────────┐
                                         │ TLS                   │ HTTPS                 │ HTTPS
                                         ▼                       ▼                       ▼
                              ┌────────────────────┐   ┌───────────────────┐   ┌───────────────────┐
                              │MongoDB Atlas (Free)│   │  Razorpay Test API│   │ Google Gemini API │
                              │ M0 512MB Cluster   │   │  & Signed Webhook │   │ GenAI Python SDK  │
                              └────────────────────┘   └───────────────────┘   └───────────────────┘
```

---

## 2. Infrastructure Specifications

### 2.1 Database: MongoDB Atlas (M0 Free Tier)
- **Tier:** M0 Sandbox (Free forever, 512 MB storage).
- **Network Access:** Whitelist Render egress IPs or allow `0.0.0.0/0` with strict credential authentication.
- **Connection String Format:** `mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority`
- **TLS:** Mandatory (`ssl=true`).

### 2.2 Backend: Render Web Service
- **Service Type:** Web Service (Python Environment).
- **Plan:** Free Tier.
- **Root Directory:** `backend`
- **Build Command:** `pip install --no-cache-dir -r requirements.txt`
- **Start Command:**
  ```bash
  uvicorn revenueos.asgi:application --host 0.0.0.0 --port $PORT --workers 1 --lifespan on
  ```
- **Health Check Path:** `/api/health/`
- **Port:** Render dynamically assigns `$PORT`. The backend binds to `0.0.0.0:$PORT`.

### 2.3 Frontend: Vercel
- **Framework Preset:** Next.js
- **Root Directory:** `frontend`
- **Build Command:** `next build`
- **Output Directory:** `.next`
- **Node.js Version:** 20.x or 22.x

---

## 3. Canonical Environment Configuration Matrix

| Variable | Platform | Classification | Purpose |
| :--- | :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | Render | Secret | Cryptographic signing of cookies and state. |
| `DJANGO_ALLOWED_HOSTS` | Render | Public | Comma-separated allowed hostnames (e.g. `revenueos-backend.onrender.com`). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Render | Public | Full URL origins for CSRF protection (e.g. `https://revenueos.vercel.app`). |
| `FRONTEND_ORIGIN` | Render | Public | Allowed browser origin for CORS and WebSocket handshake. |
| `MONGODB_URI` | Render | Secret | Atlas connection string. |
| `MONGODB_DB` | Render | Public | Database name (e.g., `revenueos`). |
| `RAZORPAY_KEY_ID` | Render | Secret | Razorpay Test API Key ID (`rzp_test_...`). |
| `RAZORPAY_KEY_SECRET` | Render | Secret | Razorpay Test API Secret. |
| `RAZORPAY_WEBHOOK_SECRET` | Render | Secret | HMAC secret for verifying incoming webhooks. |
| `GEMINI_API_KEY_1` | Render | Secret | Primary Google Gemini API key (Required or legacy GEMINI_API_KEY). |
| `GEMINI_API_KEY_2` | Render | Secret | Secondary Google Gemini API key (Optional failover slot). |
| `GEMINI_API_KEY_3` | Render | Secret | Tertiary Google Gemini API key (Optional failover slot). |
| `GEMINI_API_KEY` | Render | Secret | Backward-compatible fallback if `GEMINI_API_KEY_1` is unset. |
| `GEMINI_MODEL` | Render | Public | Selected model (default: `gemini-3.6-flash`). |
| `TURNSTILE_SECRET_KEY` | Render | Secret | Cloudflare Turnstile Server Secret for `/siteverify`. |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | Vercel | Public | Cloudflare Turnstile Client Site Key. |
| `NEXT_PUBLIC_API_ORIGIN` | Vercel | Public | Backend base URL (e.g., `https://revenueos-backend.onrender.com`). |
| `NEXT_PUBLIC_WS_URL` | Vercel | Public | Backend WebSocket URL (e.g., `wss://revenueos-backend.onrender.com/ws/v1/app/`). |

> **Critical Security Rule:** Never define any API keys, database credentials, or gateway secrets under `NEXT_PUBLIC_*`. Only client-safe origins and public site keys may be placed in the frontend bundle.

> **Important Quota Note:** Google Gemini rate limits and daily quotas (e.g., 20 requests/day on `gemini-3.6-flash` free tier) apply at the Google Cloud Project level. If multiple keys belong to the same GCP project, they share that project's quota. To achieve true quota expansion, configure keys generated across distinct Google Cloud projects. Automatic failover additionally protects against single-key invalidations and transient network failures.

---

## 4. Step-by-Step Deployment Runbook

### Phase A: MongoDB Atlas Setup
1. Create a free shared cluster (M0) in the closest region (e.g., `ap-south-1` Mumbai).
2. Create a database user `revenueos_app` with readWrite permissions on database `revenueos`.
3. Configure Network Access to allow access from any IP (`0.0.0.0/0`) since Render uses dynamic outbound IPs on the free tier.
4. Copy the SRV connection string into `MONGODB_URI`.

### Phase B: Render Backend Deployment
1. Connect your GitHub repository to Render and create a new **Web Service**.
2. Set Root Directory to `backend`.
3. Set Runtime to **Python 3**.
4. Set Build Command: `pip install --no-cache-dir -r requirements.txt`
5. Set Start Command: `uvicorn revenueos.asgi:application --host 0.0.0.0 --port $PORT --workers 1`
6. Populate all Render environment variables from Section 3.
7. Configure Health Check Path to `/api/health/`.
8. Trigger deployment and verify logs show:
   ```
   INFO: Uvicorn running on http://0.0.0.0:10000 (Press CTRL+C to quit)
   ```
9. Verify via curl:
   ```bash
   curl -i https://your-backend.onrender.com/api/health/
   # Returns HTTP 200 {"status": "healthy", "service": "RevenueOS Backend"}
   ```

### Phase C: Vercel Frontend Deployment
1. Import the repository into Vercel and select Root Directory `frontend`.
2. Configure Environment Variables:
   - `NEXT_PUBLIC_API_ORIGIN=https://your-backend.onrender.com`
   - `NEXT_PUBLIC_WS_URL=wss://your-backend.onrender.com/ws/v1/app/`
   - `NEXT_PUBLIC_TURNSTILE_SITE_KEY=your_turnstile_site_key`
3. Click **Deploy**.
4. Once built, copy your Vercel URL (e.g., `https://revenueos.vercel.app`) and update Render backend variables:
   - `FRONTEND_ORIGIN=https://revenueos.vercel.app`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://revenueos.vercel.app`

### Phase D: Razorpay Webhook Registration
1. In Razorpay Dashboard (Test Mode) -> Settings -> Webhooks.
2. Add Webhook URL: `https://your-backend.onrender.com/api/webhooks/razorpay/`
3. Secret: Enter value matching `RAZORPAY_WEBHOOK_SECRET`.
4. Active Events:
   - `payment.failed`
   - `payment.authorized`
   - `payment_link.paid`
   - `payment_link.cancelled`
   - `payment_link.expired`

---

## 5. Deployment Verification Checklist

- [ ] `/health/` responds with `200 OK`
- [ ] `/ready/` validates MongoDB Atlas connectivity
- [ ] Browser navigates to Vercel URL with no console errors
- [ ] Turnstile widget renders and completes challenge
- [ ] Login issues secure HTTP-only cookie
- [ ] WebSocket handshakes successfully with status 101 Switching Protocols
- [ ] Live ping/pong heartbeats flow over WebSocket
- [ ] Razorpay webhook delivers and verifies HMAC signature
- [ ] No secrets present in client network inspection or bundled JS

---
*RevenueOS Deployment Architecture & Runbook — Approved for Phase 0.*
