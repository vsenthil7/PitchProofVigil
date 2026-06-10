"""Render documentation screenshots of the PitchProof Vigil dashboard.

These are produced from SVG built with the *same* design tokens as the live
stylesheet (src/styles.css), so the user guide is accurately illustrated in
environments where a headless browser is unavailable. When Playwright runs in
Claude Desktop, scripts/run_e2e.sh overwrites these with true browser captures.
"""
from __future__ import annotations

import os

import cairosvg

# Design tokens mirrored from src/styles.css
PITCH_900 = "#061410"
PITCH_800 = "#0a1f18"
PITCH_700 = "#0f2c22"
LINE = "#1f4a39"
SIGNAL = "#2ce69b"
SIGNAL_DIM = "#1d9d6c"
AMBER = "#ffb347"
HAZARD = "#ff5d5d"
CHALK = "#eafff6"
CHALK_DIM = "#8fb6a6"
CHALK_FAINT = "#5a7d6f"
INK = "#04100c"

W, H = 1320, 900
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def topbar() -> str:
    pills = ""
    for i, (label, mode) in enumerate(
        [("Gemini", "mock"), ("Phoenix", "mock"), ("Arize AX", "mock")]
    ):
        x = 980 + i * 112
        dot = AMBER if mode == "mock" else SIGNAL
        col = CHALK_DIM if mode == "mock" else SIGNAL
        pills += f"""
        <rect x="{x}" y="34" width="104" height="26" rx="13" fill="none" stroke="{LINE}"/>
        <circle cx="{x + 13}" cy="47" r="3.5" fill="{dot}"/>
        <text x="{x + 24}" y="51" font-family="monospace" font-size="10" fill="{col}">{label} · {mode}</text>
        """
    return f"""
    <rect x="40" y="28" width="42" height="42" rx="11" fill="{SIGNAL}"/>
    <text x="61" y="56" font-size="22" fill="{INK}" text-anchor="middle" font-weight="bold">◎</text>
    <text x="96" y="46" font-family="sans-serif" font-size="19" font-weight="bold" fill="{CHALK}">PitchProof Vigil</text>
    <text x="96" y="64" font-family="monospace" font-size="11" fill="{CHALK_DIM}">AGENT RELIABILITY CONTROL ROOM · T1 ARIZE</text>
    {pills}
    <line x1="40" y1="92" x2="{W - 40}" y2="92" stroke="{LINE}"/>
    """


def panel(x, y, w, h, title):
    return f"""
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{PITCH_800}" stroke="{LINE}"/>
    <text x="{x + 20}" y="{y + 28}" font-family="monospace" font-size="12" fill="{CHALK_DIM}" letter-spacing="1.5">{title}</text>
    """


def eval_row(x, y, w, name, expl, verdict):
    colmap = {"pass": SIGNAL, "warn": AMBER, "fail": HAZARD}
    bg = {"pass": "rgba(44,230,155,0.12)", "warn": "rgba(255,179,71,0.12)", "fail": "rgba(255,93,93,0.14)"}
    c = colmap[verdict]
    return f"""
    <rect x="{x}" y="{y}" width="{w}" height="46" rx="8" fill="{PITCH_700}" stroke="{LINE}"/>
    <text x="{x + 14}" y="{y + 21}" font-family="monospace" font-size="11" fill="{CHALK_DIM}">{name}</text>
    <text x="{x + 14}" y="{y + 37}" font-family="sans-serif" font-size="11.5" fill="{CHALK_DIM}">{_esc(expl)}</text>
    <rect x="{x + w - 70}" y="{y + 13}" width="56" height="20" rx="6" fill="{bg[verdict]}"/>
    <text x="{x + w - 42}" y="{y + 27}" font-family="monospace" font-size="11" font-weight="bold" fill="{c}" text-anchor="middle">{verdict.upper()}</text>
    """


def metric(x, value, label, alert=False):
    col = HAZARD if alert else CHALK
    return f"""
    <rect x="{x}" y="116" width="240" height="74" rx="8" fill="{PITCH_700}" stroke="{LINE}"/>
    <text x="{x + 16}" y="156" font-family="monospace" font-size="26" font-weight="bold" fill="{col}">{value}</text>
    <text x="{x + 16}" y="178" font-family="sans-serif" font-size="11" fill="{CHALK_DIM}" letter-spacing="1">{label}</text>
    """


def base(body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
    <rect width="{W}" height="{H}" fill="{PITCH_900}"/>
    {topbar()}
    {body}
    </svg>"""


def left_console(result=None):
    s = panel(40, 116, 700, 740, "LIVE CONSOLE")
    s += f'<rect x="60" y="150" width="520" height="44" rx="8" fill="{PITCH_900}" stroke="{LINE}"/>'
    s += f'<text x="74" y="177" font-family="sans-serif" font-size="13" fill="{CHALK_FAINT}">Ask the World Cup concierge agent…</text>'
    s += f'<rect x="588" y="150" width="60" height="44" rx="8" fill="{PITCH_900}" stroke="{LINE}"/><text x="618" y="177" font-family="monospace" font-size="12" fill="{CHALK}" text-anchor="middle">EN</text>'
    s += f'<rect x="656" y="150" width="64" height="44" rx="8" fill="{SIGNAL}"/><text x="688" y="177" font-family="sans-serif" font-size="13" font-weight="bold" fill="{INK}" text-anchor="middle">Run</text>'
    chips = ["When does Spain play Germany?", "When does France play England?", "What gate for Brazil section 114?"]
    cx = 60
    for c in chips:
        wch = 16 + len(c) * 6.2
        s += f'<rect x="{cx}" y="208" width="{wch}" height="28" rx="14" fill="{PITCH_700}" stroke="{LINE}"/>'
        s += f'<text x="{cx + wch/2}" y="226" font-family="monospace" font-size="11" fill="{CHALK_DIM}" text-anchor="middle">{_esc(c)}</text>'
        cx += wch + 8
    if result:
        s += result
    return s


def answer_block(text, intent, score, evals):
    s = f'<rect x="60" y="258" width="660" height="78" rx="8" fill="{PITCH_900}" stroke="{LINE}"/>'
    s += f'<text x="76" y="288" font-family="sans-serif" font-size="15" fill="{CHALK}">{_esc(text)}</text>'
    s += f'<text x="76" y="318" font-family="monospace" font-size="11" fill="{CHALK_FAINT}">intent: {intent}    model: mock-concierge    score: {score}%</text>'
    y = 350
    for (n, e, v) in evals:
        s += eval_row(60, y, 660, n, e, v)
        y += 54
    return s


def right_column(feed_items):
    s = metric(760, "5", "TRACES OBSERVED")
    s += metric(1012, "0.18", "DRIFT DISTANCE")
    # Third tile sits below the first two as a full-width strip.
    s += f'<rect x="760" y="116" width="0" height="0"/>'
    s += panel(760, 210, 520, 646, "LIVE EVALUATION FEED")
    s += f'<circle cx="1230" cy="232" r="4" fill="{SIGNAL}"/><text x="1244" y="236" font-family="monospace" font-size="11" fill="{CHALK_DIM}" text-anchor="end" transform="translate(20,0)">streaming</text>'
    y = 250
    if not feed_items:
        s += f'<text x="1020" y="540" font-family="monospace" font-size="13" fill="{CHALK_FAINT}" text-anchor="middle">awaiting evaluation events…</text>'
    for (kind, main, score, sev) in feed_items:
        col = {"ok": SIGNAL, "warn": AMBER, "bad": HAZARD}[sev]
        s += f'<rect x="780" y="{y}" width="480" height="48" rx="8" fill="{PITCH_700}" stroke="{LINE}"/>'
        s += f'<rect x="780" y="{y}" width="3" height="48" fill="{col}"/>'
        s += f'<text x="800" y="{y + 20}" font-family="monospace" font-size="10" fill="{CHALK_FAINT}">{kind.upper()}</text>'
        s += f'<text x="800" y="{y + 38}" font-family="sans-serif" font-size="13" fill="{CHALK}">{_esc(main)}</text>'
        if score:
            s += f'<text x="1244" y="{y + 30}" font-family="monospace" font-size="13" font-weight="bold" fill="{col}" text-anchor="end">{score}</text>'
        y += 56
    return s


def gate_banner(blocked=True):
    s = panel(40, 116, 700, 740, "PROMOTION GATE")
    s += f'<rect x="60" y="150" width="520" height="44" rx="8" fill="{PITCH_900}" stroke="{LINE}"/><text x="74" y="177" font-family="monospace" font-size="13" fill="{CHALK}">prompt-v2</text>'
    s += f'<rect x="588" y="150" width="132" height="44" rx="8" fill="{SIGNAL}"/><text x="654" y="177" font-family="sans-serif" font-size="13" font-weight="bold" fill="{INK}" text-anchor="middle">Run Gate</text>'
    bcol = HAZARD if blocked else SIGNAL
    bbg = "rgba(255,93,93,0.09)" if blocked else "rgba(44,230,155,0.08)"
    icon = "✕" if blocked else "✓"
    label = "PROMOTION BLOCKED" if blocked else "PROMOTION ALLOWED"
    reason = (
        "Blocked: 1 hard failure(s). First: Kickoff mismatch: stated "
        "2026-06-18T18:00:00 but authoritative is 2026-06-18T20:00:00."
    )
    s += f'<rect x="60" y="214" width="660" height="104" rx="8" fill="{bbg}" stroke="{bcol}"/>'
    s += f'<rect x="78" y="232" width="46" height="46" rx="11" fill="rgba(255,93,93,0.16)"/>'
    s += f'<text x="101" y="264" font-size="22" font-weight="bold" fill="{bcol}" text-anchor="middle">{icon}</text>'
    s += f'<text x="140" y="248" font-family="sans-serif" font-size="16" font-weight="bold" fill="{CHALK}">{label}</text>'
    s += f'<text x="140" y="272" font-family="sans-serif" font-size="12" fill="{CHALK_DIM}">{_esc(reason[:64])}</text>'
    s += f'<text x="140" y="290" font-family="sans-serif" font-size="12" fill="{CHALK_DIM}">{_esc(reason[64:])}</text>'
    s += f'<text x="140" y="310" font-family="monospace" font-size="11" fill="{CHALK_FAINT}">candidate: prompt-v2   aggregate: 89%   threshold: 85%</text>'
    s += eval_row(60, 334, 660, "factual_accuracy", "Kickoff mismatch: stated 18:00 but authoritative is 20:00.", "fail")
    return s


def render(name: str, body: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    svg = base(body)
    path = os.path.join(OUT, name)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=path, output_width=W, output_height=H)
    print("wrote", os.path.relpath(path))


def main() -> None:
    # 01 — empty control room
    render("01-control-room.png", left_console() + right_column([]))

    # 02 — passing evaluation
    evals_pass = [
        ("factual_accuracy", "Response consistent with authoritative data.", "pass"),
        ("groundedness", "Answer is grounded or non-factual.", "pass"),
        ("translation_quality", "English response; no translation check required.", "pass"),
    ]
    render(
        "02-passing-eval.png",
        left_console(answer_block("You can manage tickets in the official FIFA app under My Tickets.", "ticketing", 100, evals_pass))
        + right_column([("trace", "Trace evaluated · intent ticketing", "100%", "ok")]),
    )

    # 03 — caught regression
    evals_fail = [
        ("factual_accuracy", "Kickoff mismatch: stated 18:00 but authoritative is 20:00.", "fail"),
        ("groundedness", "Answer is grounded or non-factual.", "pass"),
        ("translation_quality", "English response; no translation check required.", "pass"),
    ]
    render(
        "03-caught-regression.png",
        left_console(answer_block("Kickoff is at 18:00 local time at MetLife Stadium.", "kickoff_time", 67, evals_fail))
        + right_column([("trace", "Trace evaluated · intent kickoff_time", "67%", "bad")]),
    )

    # 04 — promotion blocked
    render(
        "04-promotion-blocked.png",
        gate_banner(blocked=True)
        + right_column([("gate", 'Gate "prompt-v2" → BLOCKED', "89%", "bad")]),
    )

    # 05 — live feed populated
    render(
        "05-live-feed.png",
        left_console(answer_block("For SoFi Stadium in Inglewood, CA, public transit is recommended on matchday.", "travel", 100, evals_pass))
        + right_column(
            [
                ("gate", 'Gate "prompt-v2" → BLOCKED', "89%", "bad"),
                ("trace", "Trace evaluated · intent travel", "100%", "ok"),
                ("trace", "Trace evaluated · intent kickoff_time", "67%", "bad"),
                ("trace", "Trace evaluated · intent ticketing", "100%", "ok"),
            ]
        ),
    )


if __name__ == "__main__":
    main()
