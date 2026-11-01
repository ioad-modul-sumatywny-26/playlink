#!/usr/bin/env python3
"""F4 experiment runner — variant A (all EU) vs B (split EU/US).

Run after stacks are up:
  bash scripts/local-up.sh --both
  cd experiments/f4 && python -m venv .venv && . .venv/bin/activate
  pip install -r requirements.txt
  python run.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from client import RegionClient, run_user_flow, summarize
from report import write_markdown

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Playlink F4 load experiment (1 vs 2 regions)")
    p.add_argument(
        "--variant",
        choices=["A", "B", "both"],
        default="both",
        help="A = all traffic to EU; B = split EU/US; both = run A then B",
    )
    p.add_argument("--eu", default="http://127.0.0.1:8000", help="EU API base URL")
    p.add_argument("--us", default="http://127.0.0.1:8001", help="US API base URL")
    p.add_argument("--users", type=int, default=4, help="Virtual users per variant")
    p.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Iterations per user (capped at 3 — room create quota)",
    )
    p.add_argument(
        "--pace",
        type=float,
        default=1.5,
        help="Seconds between calls (raise if you hit rate limits)",
    )
    p.add_argument(
        "--ws-samples",
        type=int,
        default=5,
        help="rooms_ws_update samples per region under test",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default results/run-<timestamp>.json)",
    )
    return p.parse_args()


async def health_ok(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{url.rstrip('/')}/healthz")
            return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


async def run_variant(
    *,
    variant: str,
    users: int,
    iterations: int,
    pace: float,
    eu: str,
    us: str,
    ws_samples: int,
) -> list:
    if variant == "A":
        targets = [("eu", eu) for _ in range(users)]
    else:
        targets = [(("eu", eu) if i % 2 == 0 else ("us", us)) for i in range(users)]

    clients = [
        RegionClient(region=region, base_url=url, variant=variant)
        for region, url in targets
    ]

    print(f"\n=== Variant {variant}: {users} users → {[c.region for c in clients]} ===")
    # return_exceptions so one broken user does not cancel the rest
    results = await asyncio.gather(
        *[run_user_flow(c, iterations=iterations, pace_s=pace) for c in clients],
        return_exceptions=True,
    )
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            print(f"  user {i} crashed: {result!r}", file=sys.stderr)

    all_samples = []
    for c in clients:
        all_samples.extend(c.samples)

    urls = {"eu": eu, "us": us}
    for region in sorted({c.region for c in clients}):
        base = urls[region]
        for i in range(ws_samples):
            observer = RegionClient(region=region, base_url=base, variant=variant)
            actor = RegionClient(region=region, base_url=base, variant=variant)
            async with observer, actor:
                if await actor.login():
                    await observer.measure_rooms_ws_update(actor)
            all_samples.extend(observer.samples)
            all_samples.extend(actor.samples)
            await asyncio.sleep(pace)
            print(f"  ws_update {region} #{i + 1}/{ws_samples}")

    return all_samples


def build_report_payload(
    *,
    args: argparse.Namespace,
    samples: list,
    started_at: str,
    finished_at: str,
) -> dict:
    by_variant: dict[str, list] = {}
    for s in samples:
        by_variant.setdefault(s.variant, []).append(s)

    scenarios = [
        "auth",
        "list_rooms",
        "create_room",
        "join_room",
        "leave_room",
        "chat_roundtrip",
        "rooms_ws_update",
    ]

    tables = {}
    for variant, subset in sorted(by_variant.items()):
        tables[variant] = {
            scenario: summarize(subset, scenario) for scenario in scenarios
        }
        tables[variant]["__all_ok__"] = summarize(subset)

    return {
        "experiment": "F4",
        "started_at": started_at,
        "finished_at": finished_at,
        "config": {
            "variant": args.variant,
            "eu": args.eu,
            "us": args.us,
            "users": args.users,
            "iterations": args.iterations,
            "pace_s": args.pace,
            "ws_samples": args.ws_samples,
            "note": (
                "Local dual-stack approximates two continents; RTT difference is small "
                "on one machine. Public EU/US URLs make the comparison meaningful."
            ),
        },
        "summary": tables,
        "samples": [s.to_dict() for s in samples],
    }


async def main_async() -> int:
    args = parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)

    if not await health_ok(args.eu):
        print(f"ERROR: EU health failed at {args.eu}/healthz", file=sys.stderr)
        print("Start stacks first: bash scripts/local-up.sh --both", file=sys.stderr)
        return 1

    variants = ["A", "B"] if args.variant == "both" else [args.variant]
    if "B" in variants and not await health_ok(args.us):
        print(
            f"ERROR: US health failed at {args.us}/healthz (needed for variant B)",
            file=sys.stderr,
        )
        print("Run: bash scripts/local-up.sh --both", file=sys.stderr)
        return 1

    started_at = datetime.now(UTC).isoformat()
    t0 = time.perf_counter()
    all_samples = []
    for variant in variants:
        samples = await run_variant(
            variant=variant,
            users=args.users,
            iterations=min(args.iterations, 3),
            pace=args.pace,
            eu=args.eu,
            us=args.us,
            ws_samples=args.ws_samples,
        )
        all_samples.extend(samples)
    finished_at = datetime.now(UTC).isoformat()

    payload = build_report_payload(
        args=args,
        samples=all_samples,
        started_at=started_at,
        finished_at=finished_at,
    )
    out = args.out or RESULTS / f"run-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path = out.with_suffix(".md")
    write_markdown(payload, md_path)

    elapsed = time.perf_counter() - t0
    print(f"\nWrote {out}")
    print(f"Wrote {md_path}")
    print(f"Elapsed {elapsed:.1f}s | samples={len(all_samples)}")
    for variant, table in payload["summary"].items():
        overall = table["__all_ok__"]
        err_rate = overall.get("error_rate")
        err_txt = f" errors={err_rate * 100:.1f}%" if err_rate is not None else ""
        if overall["p50_ms"] is not None and overall["p95_ms"] is not None:
            print(
                f"  variant {variant}: ok={overall['ok']}/{overall['n']}{err_txt} "
                f"p50={overall['p50_ms']:.1f}ms p95={overall['p95_ms']:.1f}ms"
            )
        else:
            print(f"  variant {variant}: ok={overall['ok']}/{overall['n']}{err_txt}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
