"""Turn F4 JSON results into a markdown table for the stage diary / report."""

from __future__ import annotations

from pathlib import Path
from typing import Any


SCENARIOS = [
    ("list_rooms", "GET /rooms"),
    ("create_room", "POST /rooms"),
    ("join_room", "POST /rooms/{name}/join"),
    ("leave_room", "POST /rooms/{name}/leave"),
    ("chat_roundtrip", "WS chat round-trip"),
    ("rooms_ws_update", "WS rooms list update"),
    ("auth", "Auth (nonce+verify)"),
]


def _fmt(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    cfg = payload.get("config", {})
    lines: list[str] = []
    lines.append("# F4 — wynik eksperymentu (1 vs 2 regiony)")
    lines.append("")
    lines.append(f"- Start: `{payload.get('started_at')}`")
    lines.append(f"- Koniec: `{payload.get('finished_at')}`")
    lines.append(
        f"- Users × iterations: `{cfg.get('users')} × {cfg.get('iterations')}` "
        f"(pace `{cfg.get('pace_s')}s`)"
    )
    lines.append(f"- EU API: `{cfg.get('eu')}`")
    lines.append(f"- US API: `{cfg.get('us')}`")
    lines.append("")
    lines.append("## Warunki")
    lines.append("")
    lines.append(
        "- **Wariant A** — cały ruch na EU (symulacja „jeden region”)."
    )
    lines.append(
        "- **Wariant B** — użytkownicy na przemian EU / US (symulacja dwóch regionów)."
    )
    lines.append(
        "- Na jednej maszynie różnica RTT jest mała; pełny sens ma pomiar na "
        "publicznych hostach EU/US z runbooka."
    )
    lines.append("")
    note = cfg.get("note")
    if note:
        lines.append(f"> {note}")
        lines.append("")

    summary = payload.get("summary", {})
    for variant in sorted(summary.keys()):
        table = summary[variant]
        overall = table.get("__all_ok__", {})
        lines.append(f"## Wariant {variant}")
        lines.append("")
        lines.append(
            f"Ogółem: **{overall.get('ok', 0)}/{overall.get('n', 0)}** OK, "
            f"error rate {_pct(overall.get('error_rate'))}, "
            f"p50 `{_fmt(overall.get('p50_ms'))}` ms, "
            f"p95 `{_fmt(overall.get('p95_ms'))}` ms."
        )
        lines.append("")
        lines.append("| Scenariusz | n | OK | Err% | p50 [ms] | p95 [ms] | mean [ms] |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for key, label in SCENARIOS:
            row = table.get(key, {})
            lines.append(
                "| "
                + " | ".join(
                    [
                        label,
                        str(row.get("n", 0)),
                        str(row.get("ok", 0)),
                        _pct(row.get("error_rate")),
                        _fmt(row.get("p50_ms")),
                        _fmt(row.get("p95_ms")),
                        _fmt(row.get("mean_ms")),
                    ]
                )
                + " |"
            )
        lines.append("")

    # Side-by-side comparison when both variants present
    if "A" in summary and "B" in summary:
        lines.append("## Porównanie A vs B (p95)")
        lines.append("")
        lines.append("| Scenariusz | A p95 [ms] | B p95 [ms] | Δ (B−A) |")
        lines.append("| --- | ---: | ---: | ---: |")
        for key, label in SCENARIOS:
            a = summary["A"].get(key, {}).get("p95_ms")
            b = summary["B"].get(key, {}).get("p95_ms")
            if a is None or b is None:
                delta = "—"
            else:
                delta = _fmt(b - a)
            lines.append(
                f"| {label} | {_fmt(a)} | {_fmt(b)} | {delta} |"
            )
        lines.append("")
        lines.append("## Wniosek (do uzupełnienia po odczycie liczb)")
        lines.append("")
        lines.append(
            "1. Czy wariant B poprawia p95 dla użytkowników „dalekich” "
            "(tu: ruch na US) względem A?"
        )
        lines.append(
            "2. Czy wariant B nie pogarsza p95 dla EU względem A?"
        )
        lines.append(
            "3. Jaki jest koszt/złożoność (osobny stack) vs zysk w ms — decyzja pod F6."
        )
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
