"""FitPilot API 验证脚本 v3 — with authentication support.

Smoke checks verify endpoints are reachable with correct schema.
Does NOT run full LLM-as-Judge evaluation by default — use
RUN_FULL_LLM_EVAL=1 to opt into the lengthy evaluation pipeline.
"""
import json
import os
import sys
import time

import pytest
import requests

BASE = "http://localhost:8000"

EVAL_MINIMAL_PAYLOAD = {
    "intent_cases": [
        {"message": "你好", "expected_intent": "greeting"},
        {"message": "深蹲时膝盖刺痛怎么办？", "expected_intent": "safety_concern"},
    ],
    "dialog_cases": [],
}


def _api(method, path, **kwargs):
    fn = requests.post if method == "POST" else requests.get if method == "GET" else requests.put
    return fn(f"{BASE}{path}", timeout=kwargs.pop("timeout", 120), **kwargs)


def _check(method, path, label, expect_code=200, **kwargs):
    """Single API call check, returns (label, passed)."""
    timeout_val = kwargs.pop("timeout", 300)
    print(f"\n{'='*60}")
    print(f"  {label}", flush=True)
    print(f"{'='*60}", flush=True)
    t0 = time.monotonic()
    try:
        r = _api(method, path, timeout=timeout_val, **kwargs)
        elapsed = (time.monotonic() - t0) * 1000
        print(f"  Status: {r.status_code}  ({elapsed:.0f} ms)", flush=True)
        if r.status_code == expect_code:
            ct = r.headers.get("content-type", "")
            if ct.startswith("application/json"):
                data = r.json()
                if isinstance(data, dict):
                    print(json.dumps(data, ensure_ascii=False, indent=2)[:1200], flush=True)
            return label, True
        else:
            print(f"  Body: {r.text[:1200]}", flush=True)
            return label, False
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        print(f"  FAILED ({elapsed:.0f} ms): {type(e).__name__}: {e}", flush=True)
        return label, False


def _get_auth_token():
    r = _api("POST", "/auth/register", json={
        "email": "apitest@fitpilot-test.local",
        "display_name": "API Test", "password": "TestPass123!",
    })
    if r.status_code in (200, 201):
        return r.json()["access_token"]
    r2 = _api("POST", "/auth/login", json={
        "email": "apitest@fitpilot-test.local", "password": "TestPass123!",
    })
    if r2.status_code == 200:
        return r2.json()["access_token"]
    return None


def run_all_checks():
    results = {}
    token = _get_auth_token()
    auth = {"Authorization": f"Bearer {token}"} if token else {}

    # 1. Health (public)
    results["health"] = _check("GET", "/health", "GET /health")[1]

    # 2. Knowledge stats (public)
    results["knowledge_stats"] = _check("GET", "/knowledge/stats", "GET /knowledge/stats")[1]

    # 3. Monitor (public)
    results["monitor"] = _check("GET", "/monitor", "GET /monitor")[1]

    # 4. Chat - greeting (needs auth)
    ok = _check("POST", "/chat", "POST /chat (greeting, auth)",
                json={"message": "你好"}, headers=auth)[1]
    results["chat_greeting"] = ok

    # 5. Chat - plan generation (needs auth)
    ok = _check("POST", "/chat", "POST /chat (plan generation, auth)",
                json={"message": "我是新手，只有哑铃，帮我安排三天训练计划"}, headers=auth)[1]
    results["chat_plan"] = ok

    # 6. Chat - exercise (needs auth)
    ok = _check("POST", "/chat", "POST /chat (exercise, auth)",
                json={"message": "卧推主要练哪里？动作要点是什么？"}, headers=auth)[1]
    results["chat_exercise"] = ok

    # 7. Search (needs auth)
    ok = _check("POST", "/search?query=深蹲动作要点&top_k=3",
                "POST /search (auth)", headers=auth)[1]
    results["search"] = ok

    # 8. Eval smoke — minimal intent-only payload, no dialog/LLM-judge
    ok = _check("POST", "/eval/run", "POST /eval/run (smoke, 2 intents)",
                json=EVAL_MINIMAL_PAYLOAD, headers=auth, timeout=180)[1]
    results["eval"] = ok

    print(f"\n\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for name, ok in results.items():
        print(f"  {'[OK]' if ok else '[FAIL]'} {name}")
    total_ok = sum(1 for v in results.values() if v)
    print(f"  Total: {total_ok}/{len(results)} passed")

    return results


def test_fitpilot_api():
    """pytest entry: run all API smoke checks."""
    results = run_all_checks()
    failed = [name for name, ok in results.items() if not ok]
    assert len(failed) == 0, f"Failed checks: {failed}"


@pytest.mark.integration
@pytest.mark.llm
def test_full_eval():
    """Full LLM-as-Judge evaluation (requires valid LLM API key).

    Skip by default. Run with:

        $env:RUN_FULL_LLM_EVAL = "1"
        python -m pytest tests/test_api.py::test_full_eval -s -q
    """
    if not os.getenv("RUN_FULL_LLM_EVAL"):
        pytest.skip("RUN_FULL_LLM_EVAL not set — skipping full evaluation")

    token = _get_auth_token()
    auth = {"Authorization": f"Bearer {token}"} if token else {}
    ok = _check("POST", "/eval/run", "POST /eval/run (full, defaults)",
                json={}, headers=auth, timeout=600)[1]
    assert ok, "Full eval run failed"


if __name__ == "__main__":
    run_all_checks()
