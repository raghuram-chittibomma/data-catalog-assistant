#!/usr/bin/env python
"""Call MCP HTTP endpoints (server must already be running)."""

import json
import os
import sys

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from src.utils.config_loader import load_config

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3000


def _post(base: str, path: str, payload: dict) -> dict:
    url = f"{base}{path}"
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> int:
    cfg = load_config()
    mcp = cfg.get("mcp_server", {})
    host = mcp.get("host", DEFAULT_HOST)
    port = int(mcp.get("port", DEFAULT_PORT))
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    base = f"http://{host}:{port}"

    print(f"MCP smoke against {base}\n")

    try:
        root = requests.get(f"{base}/", timeout=10)
        root.raise_for_status()
        print("[ok] GET /")
    except requests.RequestException as e:
        print(f"[fail] Server not reachable at {base} — start: python src\\main.py\n       {e}")
        return 1

    search = _post(base, "/tools/search_data_assets", {"query": "customer orders", "top_k": 3})
    total = search.get("total", 0)
    print(f"[ok] search_data_assets -> {total} hit(s)")
    if total == 0:
        print("     Run batch_jobs/run_refresh_job.py first")

    lineage = _post(
        base,
        "/tools/get_lineage",
        {"data_asset": "public.orders", "direction": "both"},
    )
    print(f"[ok] get_lineage -> keys: {list(lineage.keys())}")

    summary = requests.post(f"{base}/resources/data_catalog_summary", json={}, timeout=30)
    summary.raise_for_status()
    print(f"[ok] data_catalog_summary -> {summary.json()}")

    print("\nMCP smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
