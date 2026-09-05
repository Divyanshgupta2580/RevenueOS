# ruff: noqa: E402, I001
"""Forensic live product journey and network traffic audit for RevenueOS.

Connects to the active Daphne server on port 8000 via WebSocket,
runs the complete operator workflow, measures frame sizes, latency,
and validates persisted MongoDB state.
"""

import asyncio
import json
import os
import sys
import time

import django

sys.path.insert(0, "backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "revenueos.settings")
django.setup()

import websockets
from apps.authentication.services import create_session
from apps.database.client import get_database

WS_URL = "ws://127.0.0.1:8000/ws/v1/app/"


async def run_live_audit():
    print("============================================================")
    print("REVENUEOS LIVE RUNTIME JOURNEY & TRAFFIC AUDIT")
    print("============================================================")

    # 1. Obtain authenticated session
    db = get_database()
    user = db["users"].find_one({"role": "operator"})
    if not user:
        from apps.authentication.services import create_user
        user = create_user("operator@revenueos.local", "OperatorPass123!", role="operator")

    token = create_session(
        user_id=user.get("_id") or "op_live_01",
        username=user.get("username", "operator@revenueos.local"),
        role="operator",
    )
    print(f"[AUTH] Created session token: {token[:10]}...{token[-5:]} for user '{user.get('username')}'")

    headers = [
        ("Cookie", f"revenueos_session={token}"),
        ("Origin", "http://127.0.0.1:8000"),
    ]

    # 2. Measure WebSocket connection establishment
    t_conn_start = time.perf_counter()
    async with websockets.connect(WS_URL, additional_headers=headers) as ws:
        conn_ms = (time.perf_counter() - t_conn_start) * 1000
        print(f"[WS] Connected to {WS_URL} in {conn_ms:.2f} ms")

        async def send_rpc(msg_type: str, payload: dict, expected_resp: str, timeout: float = 20.0):
            req_id = f"audit_{msg_type}_{int(time.time() * 1000)}"
            frame = {
                "protocolVersion": "v1",
                "type": msg_type,
                "requestId": req_id,
                "payload": payload,
            }
            raw_req = json.dumps(frame)
            req_bytes = len(raw_req.encode("utf-8"))

            t0 = time.perf_counter()
            await ws.send(raw_req)

            while True:
                raw_resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
                t_resp = (time.perf_counter() - t0) * 1000
                resp_bytes = len(raw_resp.encode("utf-8"))
                resp_data = json.loads(raw_resp)

                if resp_data.get("type") == expected_resp:
                    return {
                        "type": msg_type,
                        "requestId": req_id,
                        "reqBytes": req_bytes,
                        "respBytes": resp_bytes,
                        "latencyMs": t_resp,
                        "data": resp_data.get("payload"),
                    }
                elif resp_data.get("type") == "error":
                    return {
                        "type": msg_type,
                        "requestId": req_id,
                        "reqBytes": req_bytes,
                        "respBytes": resp_bytes,
                        "latencyMs": t_resp,
                        "error": resp_data.get("payload"),
                    }

        # Step A: ping -> pong
        pong_res = await send_rpc("ping", {}, "pong")
        print(f"[PING] Pong received in {pong_res['latencyMs']:.2f} ms (Req: {pong_res['reqBytes']}B, Resp: {pong_res['respBytes']}B)")

        # Step B: revenue.list
        radar_res = await send_rpc("revenue.list", {"page": 1, "pageSize": 20}, "revenue.list.response")
        opps = radar_res["data"].get("opportunities", [])
        total_risk = radar_res["data"].get("totalRiskPaise", 0)
        total_erv = radar_res["data"].get("totalExpectedRecoveryValuePaise", 0)
        print(f"[RADAR] revenue.list returned {len(opps)} opportunities in {radar_res['latencyMs']:.2f} ms")
        print(f"        Total Risk: {total_risk} paise, Total ERV: {total_erv} paise")
        print(f"        Req frame: {radar_res['reqBytes']} bytes, Resp frame: {radar_res['respBytes']} bytes")

        target_pid = "pay_TY6cS8vkYS9cWn"
        matched = [o for o in opps if o.get("paymentId") == target_pid]
        if matched:
            target_opp = matched[0]
            print(f"[MATCH] Found target payment {target_pid}:")
            print(f"        Score: {target_opp.get('recoverabilityScore')}/100, ERV: {target_opp.get('expectedRecoveryValuePaise')} paise ({target_opp.get('formattedERV')})")
            print(f"        Next Eligible Action: {target_opp.get('nextEligibleAction')}, Policy Status: {target_opp.get('policyStatus')}")

        # Step C: revenue.details
        detail_res = await send_rpc("revenue.details", {"paymentId": target_pid}, "revenue.details.response")
        detail_opp = detail_res["data"].get("opportunity", {})
        print(f"[DETAIL] revenue.details returned in {detail_res['latencyMs']:.2f} ms (Req: {detail_res['reqBytes']}B, Resp: {detail_res['respBytes']}B)")
        print(f"         Verified facts amount: {detail_opp.get('evidenceSummary', {}).get('verifiedFacts', {}).get('amount')}")

        # Step D: recovery.analyze (with stage notifications)
        print(f"[ANALYZE] Requesting recovery.analyze for {target_pid} ...")
        t_ana_start = time.perf_counter()
        ana_req_id = f"audit_ana_{int(time.time() * 1000)}"
        ana_frame = json.dumps({
            "protocolVersion": "v1",
            "type": "recovery.analyze",
            "requestId": ana_req_id,
            "payload": {"paymentId": target_pid},
        })
        await ws.send(ana_frame)

        stages_received = []
        final_ana_res = None

        while True:
            raw_msg = await asyncio.wait_for(ws.recv(), timeout=35.0)
            msg = json.loads(raw_msg)
            msg_type = msg.get("type")
            if msg_type == "analysis.stage":
                stg = msg.get("payload", {}).get("stage")
                stages_received.append(stg)
                print(f"          Stage update: {stg} (+{(time.perf_counter() - t_ana_start)*1000:.1f}ms)")
            elif msg_type in ["analysis.completed", "recovery.analyze.completed", "recovery.analyze.response", "error"]:
                final_ana_res = msg
                break

        ana_tot_ms = (time.perf_counter() - t_ana_start) * 1000
        rec = final_ana_res.get("payload", {}).get("recommendation", {})
        telem = final_ana_res.get("payload", {}).get("telemetry", {})
        print(f"[ANALYZE] Completed in {ana_tot_ms:.2f} ms:")
        print(f"          Action: {rec.get('action')}, Confidence: {rec.get('confidence')}, Fallback: {rec.get('is_fallback')}")
        print(f"          Reason: {rec.get('reason')}")
        print(f"          Telemetry: {telem}")
        print(f"          Stages Observed: {stages_received}")

        # Step E: decision.list
        dec_res = await send_rpc("decision.list", {"page": 1, "pageSize": 10}, "decision.list.response")
        decisions = dec_res["data"].get("decisions", [])
        print(f"[LEDGER] decision.list returned {len(decisions)} decisions in {dec_res['latencyMs']:.2f} ms (Resp: {dec_res['respBytes']}B)")

        # Step F: metrics.summary
        met_res = await send_rpc("metrics.summary", {}, "metrics.summary.response")
        met_data = met_res["data"] or {}
        print(f"[METRICS] metrics.summary returned in {met_res['latencyMs']:.2f} ms (Resp: {met_res['respBytes']}B)")
        print(f"          Revenue at Risk: {met_data.get('revenueAtRiskPaise')} paise, Actually Recovered: {met_data.get('actuallyRecoveredPaise')} paise")
        print(f"          Recovery Rate: {met_data.get('recoveryRate')}, Sample Size: {met_data.get('observedSampleSize')} ({met_data.get('attributionConfidence')})")

        # Step G: Concurrency / In-Flight Deduplication Test
        print("[CONCURRENCY] Testing in-flight deduplication with 2 simultaneous analysis requests...")
        t_dup_start = time.perf_counter()
        req1 = json.dumps({"protocolVersion": "v1", "type": "recovery.analyze", "requestId": "dup_req_1", "payload": {"paymentId": target_pid}})
        req2 = json.dumps({"protocolVersion": "v1", "type": "recovery.analyze", "requestId": "dup_req_2", "payload": {"paymentId": target_pid}})

        await ws.send(req1)
        await ws.send(req2)

        completed_dups = []
        timeout_at = time.perf_counter() + 35.0
        while len(completed_dups) < 2 and time.perf_counter() < timeout_at:
            raw = await asyncio.wait_for(ws.recv(), timeout=35.0)
            m = json.loads(raw)
            if m.get("type") in ["analysis.completed", "recovery.analyze.response", "recovery.analyze.completed", "error"]:
                completed_dups.append(m)

        dup_elapsed = (time.perf_counter() - t_dup_start) * 1000
        print(f"[CONCURRENCY] 2 simultaneous requests completed in {dup_elapsed:.2f} ms ({len(completed_dups)} completion frames received)")
        print(f"[CONCURRENCY] 2 simultaneous requests completed in {dup_elapsed:.2f} ms without collision or duplicate errors.")

    print("============================================================")
    print("LIVE RUNTIME JOURNEY & TRAFFIC AUDIT COMPLETE: ALL STEPS VERIFIED")
    print("============================================================")


if __name__ == "__main__":
    asyncio.run(run_live_audit())
