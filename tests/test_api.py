"""FitPilot API 验证脚本 v2 (ASCII safe)"""
import json
import sys
import requests

BASE = "http://localhost:8000"


def _check(method, path, label, **kwargs):
    """单次 API 调用检查，返回 (label, passed)."""
    print(f"\n{'='*60}")
    print(f"  {label}", flush=True)
    print(f"{'='*60}", flush=True)
    try:
        if method == "GET":
            r = requests.get(f"{BASE}{path}", timeout=120, **kwargs)
        else:
            r = requests.post(f"{BASE}{path}", timeout=120, **kwargs)
        print(f"  Status: {r.status_code}", flush=True)
        if r.status_code == 200:
            data = r.json()
            print(json.dumps(data, ensure_ascii=False, indent=2)[:800], flush=True)
            return label, True
        else:
            print(f"  Body: {r.text[:500]}", flush=True)
            return label, False
    except Exception as e:
        print(f"  FAILED: {e}", flush=True)
        return label, False


def run_all_checks():
    """运行所有 API 检查，返回结果字典。"""
    results = {}

    # 1. Health
    label, ok = _check("GET", "/health", "GET /health")
    results[label] = ok

    # 2. Knowledge stats
    label, ok = _check("GET", "/knowledge/stats", "GET /knowledge/stats")
    results[label] = ok

    # 3. Monitor
    label, ok = _check("GET", "/monitor", "GET /monitor")
    results[label] = ok

    # 4. Chat - greeting
    label, ok = _check("POST", "/chat", "POST /chat (greeting)",
        json={"message": "你好"})
    results[label] = ok

    # 5. Chat - fitness plan generation
    label, ok = _check("POST", "/chat", "POST /chat (plan generation)",
        json={"message": "我是新手，只有哑铃，帮我安排一个三天训练计划"})
    results[label] = ok

    # 6. Chat - exercise query
    label, ok = _check("POST", "/chat", "POST /chat (exercise)",
        json={"message": "卧推主要练哪里？动作要点是什么？"})
    results[label] = ok

    # 7. Search
    label, ok = _check("POST", "/search?query=深蹲动作要点&top_k=3", "POST /search")
    results[label] = ok

    # 8. Eval
    label, ok = _check("POST", "/eval/run", "POST /eval/run", json={})
    results[label] = ok

    print(f"\n\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for name, ok in results.items():
        print(f"  {'[OK]' if ok else '[FAIL]'} {name}")
    total_ok = sum(1 for v in results.values() if v)
    print(f"  Total: {total_ok}/{len(results)} passed")

    return results


# ── 支持两种运行方式：直接 python script 或 pytest ──────────────────────────

def test_fitpilot_api():
    """pytest 入口：运行所有 API 检查，失败时抛出 AssertionError。"""
    results = run_all_checks()
    failed = [name for name, ok in results.items() if not ok]
    assert len(failed) == 0, f"Failed checks: {failed}"


if __name__ == "__main__":
    run_all_checks()
