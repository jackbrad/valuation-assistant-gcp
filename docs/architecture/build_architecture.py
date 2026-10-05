"""Builds the architecture diagram (architecture.svg and architecture.png).

Icons are the official Google Cloud icons from https://cloud.google.com/icons
(core product icons where they exist, otherwise the legacy set). Gemini runs on
Gemini Enterprise Agent Platform (formerly Vertex AI); the icon set still names
its icon Vertex AI, so Agent Platform cards use that icon.

Run from the repository root:
    python docs/architecture/build_architecture.py
    rsvg-convert -w 2400 docs/architecture/architecture.svg -o docs/architecture/architecture.png
    rsvg-convert -w 2400 docs/architecture/architecture-slide.svg -o docs/architecture/architecture-slide.png
"""
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICONS = HERE / "icons"

BLUE = "#1A73E8"
INK = "#202124"
MUTED = "#5F6368"
LINE = "#DADCE0"
FONT = "Google Sans, Roboto, Arial, sans-serif"

out: list[str] = []


def icon(name: str, x: float, y: float, size: float) -> None:
    data = base64.b64encode((ICONS / f"{name}.svg").read_bytes()).decode()
    out.append(f'<image x="{x}" y="{y}" width="{size}" height="{size}" href="data:image/svg+xml;base64,{data}"/>')


def text(x: float, y: float, s: str, size: int = 14, color: str = MUTED, weight: int = 400, anchor: str = "start") -> None:
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    out.append(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
               f'fill="{color}" text-anchor="{anchor}">{s}</text>')


def box(x: float, y: float, w: float, h: float, fill: str = "#FFFFFF", stroke: str = LINE,
        dashed: bool = False, radius: int = 12, width: float = 1.5) -> None:
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" '
               f'stroke="{stroke}" stroke-width="{width}"{dash}/>')


def step(n: int, x: float, y: float) -> None:
    out.append(f'<circle cx="{x}" cy="{y}" r="14" fill="{BLUE}"/>')
    text(x, y + 5, str(n), 14, "#FFFFFF", 700, "middle")


def arrow(points: list[tuple[float, float]], both: bool = False, dashed: bool = False) -> None:
    d = " ".join(("M" if i == 0 else "L") + f"{x},{y}" for i, (x, y) in enumerate(points))
    start = ' marker-start="url(#head)"' if both else ""
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out.append(f'<path d="{d}" fill="none" stroke="{BLUE}" stroke-width="2"{dash} marker-end="url(#head)"{start}/>')


def card(n: int | None, icon_name: str, x: float, y: float, w: float, h: float,
         title: list[str], lines: list[str], dashed: bool = False) -> None:
    box(x, y, w, h, dashed=dashed)
    icon(icon_name, x + 16, y + 16, 48)
    if n is not None:
        step(n, x + w - 26, y + 28)
    ty = y + 92
    for t in title:
        text(x + 16, ty, t, 17, INK, 600)
        ty += 22
    for line in lines:
        text(x + 16, ty, line, 14)
        ty += 20


W, H = 1800, 1060
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
out.append(f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker></defs>')
out.append(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')

# Title
text(40, 52, "Valuation assistant on Google Cloud", 28, INK, 600)
text(40, 82, "Prototype architecture. Numbered steps match the README.", 16)

# External: source systems and users
box(40, 160, 220, 270, fill="#F8F9FA")
text(56, 192, "Source systems", 17, INK, 600)
for i, (a, b) in enumerate([("Loan origination", "Appraisals"), ("Loan servicing", "Inspections"),
                            ("County data feed", "Public records"), ("Uploads", "Permits, evidence")]):
    y = 212 + i * 52
    box(56, y, 188, 44, radius=8)
    text(68, y + 19, a, 13, INK, 600)
    text(68, y + 36, b, 12)

box(40, 590, 220, 150, fill="#F8F9FA")
text(56, 622, "Users", 17, INK, 600)
for i, line in enumerate(["Appraisal reviewers", "Data stewards", "Loan officers", "(web browser)"]):
    text(56, 648 + i * 20, line, 14)

# Google Cloud boundary
box(290, 110, 1470, 900, fill="#F8F9FA", stroke="#BDC1C6", radius=16, width=2)
text(312, 144, "Google Cloud", 18, INK, 600)
text(1740, 144, "Project: us-central1 · BigQuery US", 13, MUTED, 400, "end")

# Lane 1: ingest and clean
text(320, 186, "INGEST AND CLEAN", 13, BLUE, 700)
cards = [
    (1, "cloud-storage", ["Cloud Storage"], ["Landing bucket", "One folder per", "source system"]),
    (2, "document-ai", ["Document AI"], ["Layout Parser", "Sections, tables, and", "page numbers"]),
    (3, "vertex-ai", ["Agent Platform"], ["Gemini 2.5 Flash", "Typed facts with page", "and source quote"]),
    (4, "cloud-run", ["Data quality gate"], ["Python on Cloud Run", "Conflicts with the", "record held for review"]),
    (5, "vertex-ai", ["Agent Platform"], ["text-embedding-005", "768-dimension vector", "per paragraph"]),
]
for i, (n, ic, title, lines) in enumerate(cards):
    card(n, ic, 320 + i * 240, 200, 210, 200, title, lines)
    if i < len(cards) - 1:
        arrow([(530 + i * 240, 300), (560 + i * 240, 300)])
arrow([(260, 300), (320, 300)])  # sources -> landing bucket
arrow([(1490, 300), (1530, 300)])  # embeddings -> BigQuery

# BigQuery: store, retrieve, and model
box(1530, 200, 210, 560)
icon("bigquery", 1546, 216, 48)
step(6, 1714, 228)
y = 292
text(1546, y, "BigQuery", 17, INK, 600)
for line in ["val_raw: parsed blocks", "val_core: facts with", "citations, chunks,", "vectors, and sales",
             "Retrieval:", "VECTOR_SEARCH"]:
    y += 20
    text(1546, y, line, 14)
out.append(f'<line x1="1546" y1="{y + 18}" x2="1724" y2="{y + 18}" stroke="{LINE}" stroke-width="1.5"/>')
y += 46
text(1546, y, "BigQuery ML", 17, INK, 600)
for line in ["Linear regression:", "adjustment rates", "ARIMA_PLUS: market", "index and forecast",
             "Boosted tree: price", "model (avm_v1)"]:
    y += 20
    text(1546, y, line, 14)

# Lane 2: serve, explain, and govern
text(320, 506, "SERVE, EXPLAIN, AND GOVERN", 13, BLUE, 700)
card(None, "identity-aware-proxy", 320, 540, 210, 180, ["Identity-Aware", "Proxy"], ["Planned for", "production"], dashed=True)

box(560, 520, 690, 260)
icon("cloud-run", 576, 536, 48)
text(636, 560, "Cloud Run", 17, INK, 600)
text(636, 581, "val-valuation-app (FastAPI)", 14)
subs = [
    (7, "Gemini agent", ["Tools: find property,", "search documents,", "run valuation"]),
    (8, "Valuation engine", ["Comparable sales,", "BigQuery ML rates,", "safety checks"]),
    (9, "Review workflow", ["Flags, two approvers,", "live ingestion,", "explainability"]),
]
for i, (n, title, lines) in enumerate(subs):
    sx = 576 + i * 222
    box(sx, 604, 210, 156, fill="#F8F9FA", radius=10)
    step(n, sx + 186, 628)
    text(sx + 14, 634, title, 15, INK, 600)
    for j, line in enumerate(lines):
        text(sx + 14, 660 + j * 20, line, 13)

card(None, "vertex-ai", 1280, 540, 210, 200, ["Agent Platform"], ["Gemini 2.5 Flash", "Function calling", "for the agent"])

arrow([(260, 665), (320, 665)], both=True)          # users <-> IAP
arrow([(530, 640), (560, 640)], both=True)          # IAP <-> Cloud Run
arrow([(1250, 640), (1280, 640)], both=True)        # Cloud Run <-> Gemini
arrow([(905, 520), (905, 460), (1530, 460)])  # Cloud Run -> BigQuery (queries)
text(920, 434, "Queries: VECTOR_SEARCH, facts,", 13, MUTED)
text(920, 451, "sales, BigQuery ML outputs", 13, MUTED)
arrow([(1020, 780), (1020, 820), (1680, 820), (1680, 760)])  # review workflow -> BigQuery (feedback)
arrow([(1200, 604), (1200, 400)], both=True)  # review workflow <-> ingestion (Parse now, held facts)
text(1212, 498, "Parse now runs", 12, MUTED)
text(1212, 514, "steps 1–5; held", 12, MUTED)
text(1212, 530, "facts open reviews", 12, MUTED)
text(1350, 812, "Feedback loop: approved corrections update facts; models retrain on closed sales", 13, MUTED, 400, "middle")

# Planned for production
text(320, 868, "PLANNED FOR PRODUCTION", 13, BLUE, 700)
for i, (ic, name, line) in enumerate([("pubsub", "Pub/Sub", "Events for flags and corrections"),
                                      ("cloud-scheduler", "Cloud Scheduler", "Monthly retraining, drift checks"),
                                      ("cloud-monitoring", "Cloud Monitoring", "Dashboards, SLOs, and alerts")]):
    x = 320 + i * 470
    box(x, 884, 440, 92, dashed=True)
    icon(ic, x + 16, 902, 52)
    text(x + 84, 922, name, 16, INK, 600)
    text(x + 84, 946, line, 14)

# Legend
text(1760, 1040, "Solid: built in the prototype   ·   Dashed: planned for production   ·   Icons: Google Cloud official icon set",
     13, MUTED, 400, "end")

out.append("</svg>")
svg = "\n".join(out)
(HERE / "architecture.svg").write_text(svg)
# Slide variant: same drawing, cropped to the diagram (no title or legend).
(HERE / "architecture-slide.svg").write_text(
    svg.replace(f'width="{W}" height="{H}" viewBox="0 0 {W} {H}"', 'width="1760" height="920" viewBox="20 100 1760 920"', 1))
print(f"Wrote {HERE / 'architecture.svg'} and architecture-slide.svg")
