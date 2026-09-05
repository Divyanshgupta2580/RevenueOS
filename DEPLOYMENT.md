# RevenueOS Production Deployment Guide

This guide outlines the deployment architecture, configuration steps, and environment verification for deploying RevenueOS to free-tier cloud infrastructure:
- **Frontend**: Vercel (Next.js 16 App Router)
- **Backend**: Render (Django 5, Django Channels, Daphne ASGI)
- **Database**: MongoDB Atlas (M0 Free Tier)

---

## 1. Production Architecture Topology

```
Browser (Operator Client)
    |
    +---- HTTPS: https://revenueos.vercel.app (Static Assets, App UI)
    |
    +---- WSS:   wss://<RENDER_EXTERNAL_HOSTNAME>/ws/v1/app/ (Live Socket)
    |
    v
Render Web Service (Django Channels + Daphne ASGI)
    |
    +---- Direct Driver (PyMongo) ----> MongoDB Atlas M0 (Persistent Collections)
    |
    +---- Official SDK (google-genai) -> Google Gemini API (GEMINI_MODEL)
    |
    +---- REST HTTPS Calls -----------> Razorpay Test API
    |
    <---- Inbound HTTPS Webhooks <----- Razorpay Events (/api/webhooks/razorpay/)
```

> **Key Rule**: The persistent WebSocket server lives exclusively on Render. Vercel is used solely for serving the Next.js static and serverless frontend bundle.

---

## 2. Environment Variables Specification

### A. Render Backend Environment Variables

| Variable | Description | Example / Default |
|---|---|---|
| `PYTHONPATH` | Python module import root | `backend` |
| `DJANGO_SETTINGS_MODULE` | Active Django settings | `revenueos.settings` |
| `DJANGO_SECRET_KEY` | Strong random secret for cryptographic signing | Random 50+ chars |
| `DJANGO_DEBUG` | Production debug flag (must be false) | `false` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames (Render host auto-detected via `RENDER_EXTERNAL_HOSTNAME`) | `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF protection | `https://revenueos.vercel.app` |
| `FRONTEND_ORIGIN` | Allowed CORS origin for session credentials | `https://revenueos.vercel.app` |
| `MONGODB_URI` | MongoDB Atlas connection string | `mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority` |
| `MONGODB_DB` | Production database name | `revenueos_production` |
| `RAZORPAY_KEY_ID` | Razorpay Test Mode Key ID | `rzp_test_...` |
| `RAZORPAY_KEY_SECRET` | Razorpay Test Mode Key Secret | Secret string |
| `RAZORPAY_WEBHOOK_SECRET` | Secret configured in Razorpay Dashboard for webhook signatures | Webhook secret string |
| `GEMINI_API_KEY_1` | Primary Google Gemini API key (Required or legacy GEMINI_API_KEY) | API key string |
| `GEMINI_API_KEY_2` | Secondary Google Gemini API key (Optional failover slot) | API key string |
| `GEMINI_API_KEY_3` | Tertiary Google Gemini API key (Optional failover slot) | API key string |
| `GEMINI_API_KEY` | Backward-compatible fallback if `GEMINI_API_KEY_1` is unset | API key string |
| `GEMINI_MODEL` | Gemini model variant | `gemini-3.6-flash` |

### B. Vercel Frontend Environment Variables

| Variable | Description | Example / Default |
|---|---|---|
| `NEXT_PUBLIC_API_ORIGIN` | Backend HTTP API base URL | `https://revenueos-backend.onrender.com` |
| `NEXT_PUBLIC_WS_URL` | Backend WebSocket endpoint | `wss://revenueos-backend.onrender.com/ws/v1/app/` |
| `NEXT_PUBLIC_RAZORPAY_KEY_ID` | Razorpay Test Mode Key ID | `rzp_test_...` |

---

## 3. Deployment Steps

### Step 1: MongoDB Atlas (Free Tier M0)
1. Log in to MongoDB Atlas and create an `M0 Free Cluster`.
2. Under **Network Access**, add `0.0.0.0/0` (allow access from Render dynamic IPs).
3. Under **Database Access**, create a user with read/write privileges on `revenueos_production`.
4. Copy the connection string format:
   `mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`

### Step 2: Render Backend Web Service
1. Connect your GitHub repository to Render.
2. Select **Blueprint** to use `render.yaml` or create a **Web Service**:
   - **Environment**: `Python`
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `daphne -b 0.0.0.0 -p $PORT revenueos.asgi:application`
   - **Health Check Path**: `/api/health/`
3. Add the required environment variables under the **Environment** tab.
4. Deploy the service and verify `/api/health/` returns `200 OK`.

### Step 3: Vercel Frontend
1. Import the repository into Vercel.
2. Set the **Root Directory** to `frontend`.
3. Set **Framework Preset** to `Next.js`.
4. Under **Environment Variables**, set:
   - `NEXT_PUBLIC_API_ORIGIN`
   - `NEXT_PUBLIC_WS_URL`
   - `NEXT_PUBLIC_RAZORPAY_KEY_ID`
5. Deploy. Verify build succeeds and all static pages render without hydration errors.

### Step 4: Razorpay Webhooks Configuration
1. Open Razorpay Dashboard in **Test Mode**.
2. Navigate to **Settings** -> **Webhooks** -> **Add New Webhook**.
3. Set **Webhook URL** to:
   `https://revenueos-backend.onrender.com/api/webhooks/razorpay/`
4. Set **Secret** to match `RAZORPAY_WEBHOOK_SECRET`.
5. Subscribe to events:
   - `payment.captured`
   - `payment.failed`
   - `payment_link.paid`

---

## 4. Verification & Health Probes

### Liveness Probe (Canonical: `/api/health/`, Alias: `/health/`)
```bash
curl -I https://revenueos-backend.onrender.com/api/health/
# HTTP/1.1 200 OK
# Content-Type: application/json
```

### Readiness Probe (Includes MongoDB Connection Check)
```bash
curl https://revenueos-backend.onrender.com/ready/
# {"status": "ready", "service": "RevenueOS Backend", "database": "connected"}
```

---

## 5. Free-Tier Operational Constraints
- **Render Free Tier Spin-Down**: Free Render web services spin down after 15 minutes of inactivity. First incoming requests take 30-50s to cold start. The frontend WebSocket client includes exponential backoff with automatic reconnection.
- **MongoDB Atlas Free Limits**: 512MB storage and 100 concurrent connections. RevenueOS uses singleton connection pooling and indexed bounded queries.
- **Gemini Free Tier Rate Limits**: 15 RPM (Requests Per Minute) for Gemini 3.6 Flash free tier. Guarded Autopilot gates requests and handles rate limits with safe fallback.
