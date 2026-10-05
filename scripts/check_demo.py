"""End-to-end check of the demo against a running app. Leaves the demo reset.

Usage: uv run python scripts/check_demo.py [base_url]
"""
import json, re, sys, time, urllib.parse, urllib.request

U = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
results = []


def rec(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")


def get(path):
    try:
        r = urllib.request.urlopen(U + path, timeout=60)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def post(path, data):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    try:
        req = urllib.request.Request(U + path, data=urllib.parse.urlencode(data).encode(), method="POST")
        return urllib.request.build_opener(NoRedirect).open(req, timeout=180).status
    except urllib.error.HTTPError as e:
        return e.code


def chat(q, hist=None):
    t = time.time()
    req = urllib.request.Request(U + "/api/chat", data=json.dumps({"message": q, "history": hist or []}).encode(),
                                 headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120)), time.time() - t


rec("reset", post("/api/demo/reset", {}) == 303)
for p in ["/", "/review", "/review?user=jordan.lo", "/health", "/static/chat.js", "/static/chat.css",
          "/static/pages.css", "/static/common.js", "/clearline/tokens/tokens.css", "/clearline/components/clearline.css"]:
    rec(f"GET {p}", get(p)[0] == 200)
for img in ["DOC-INS-000014-1", "DOC-INS-000014-2", "DOC-APP-000014-1", "DOC-APP-000022-1",
            "DOC-PERMIT-CH-24-0817-1", "DOC-INS-001640-1", "DOC-INS-001640-2"]:
    s, b = get(f"/static/doc_pages/{img}.png")
    rec(f"page image {img}", s == 200 and b[:4] == b"\x89PNG")
h = get("/")[1].decode()
rec("start page: 5 scenarios", h.count('class="scenario chip"') == 5)
h = get("/review")[1].decode()
rec("review: only the seeded 22 Hilltop item", "22 Hilltop Rd" in h and h.count('class="cl-card review-item"') == 1)
rec("review as Jordan: stake banner", "is the loan officer" in get("/review?user=jordan.lo")[1].decode())
h = get("/health")[1].decode()
rec("health: Riverside stricter checks", "Stricter checks on" in h and "Riverside" in h)

expected = {"What's 14 Larkspur Ln worth? It's a refi.": "appraiser", "What is 18 Larkspur Ln worth?": "shown",
            "What is 22 Hilltop Rd worth?": "appraiser", "What is 31 Mill Race Dr worth?": "appraiser",
            "What is 7 Wren Ct worth?": "appraiser"}
first = None
for q, gate in expected.items():
    d, s = chat(q)
    v = d.get("valuation") or {}
    tools = [x["tool"] for x in d["steps"]]
    good = (v.get("gate_result") == gate and "resolve_property" in tools and "run_valuation" in tools
            and not (gate == "appraiser" and "range_low" in v) and d.get("calculation") and d.get("replayed") is None)
    rec(f"scenario: {q[:32]}", good, f"{s:.1f}s {d['model']} gate={v.get('gate_result')}")
    if q.startswith("What's 14"):
        first = d
rec("14 Larkspur cites inspection p.2", "DOC-INS-000014 p.2" in first["answer"])
rec("14 Larkspur issue is flaggable", any(i.get("flag") for i in first["issues"]))
rec("14 Larkspur calculation: 3 used, 2 checks fail",
    len(first["calculation"]["comps"]) == 3 and sum(not c["ok"] for c in first["calculation"]["checks"]) == 2)

hist = [{"role": "user", "text": "What's 14 Larkspur Ln worth? It's a refi."}, {"role": "model", "text": first["answer"]}]
d, s = chat("What does the permit say?", hist)
rec("follow-up: permit", "PERMIT" in d["answer"], f"{s:.1f}s")
d, s = chat("Why were most of the nearby sales set aside?", hist)
rec("follow-up: set aside", re.search(r"\b9\b|nine", d["answer"], re.I), f"{s:.1f}s")
d, s = chat("What if the living area is really 2,080 sq ft?", hist)
rec("follow-up: what-if refused", not re.search(r"\$\d", d["answer"]), f"{s:.1f}s")

rec("flag submitted", post("/api/flags", {"property_id": "P-000014", "field_name": "gla_sqft", "proposed_value": "2080",
                                           "reason": "Stale record: 2024 addition",
                                           "evidence_desc": "DOC-INS-000014 p.2; DOC-PERMIT-CH-24-0817 p.1",
                                           "user_id": "alex.reviewer"}) == 303)
m = re.search(r'(REV-\d+) · Living area</div>\s*<h3 class="cl-card-title"><a[^>]*>14 Larkspur', get("/review")[1].decode())
item = m.group(1) if m else "missing"
rec("flag appears in queue", m)
rec("loan officer blocked (403)", post(f"/api/review/{item}/approve", {"user_id": "jordan.lo"}) == 403)
rec("flagger blocked (403)", post(f"/api/review/{item}/approve", {"user_id": "alex.reviewer"}) == 403)
rec("approver 1 (Sam)", post(f"/api/review/{item}/approve", {"user_id": "sam.reviewer"}) == 303)
rec("approver 2 (Pat)", post(f"/api/review/{item}/approve", {"user_id": "pat.steward"}) == 303)
d, s = chat("What is 14 Larkspur Ln worth now?")
v = d["valuation"]
rec("after correction: $452,438 - $525,302", v["gate_result"] == "shown" and round(v["range_low"]) == 452438
    and round(v["range_high"]) == 525302, f"{s:.1f}s")

d, s = chat("What is 18 Larkspur Ln worth?")
rec("18 Larkspur: Parse now offered", any(x.get("can_ingest") for x in d["documents"]))
t = time.time()
events = [json.loads(line) for line in urllib.request.urlopen(
    urllib.request.Request(U + "/api/ingest/DOC-INS-001640", method="POST"), timeout=180)]
rec("ingest: 6 steps and a held conflict",
    [e["step"] for e in events if e["status"] == "done"] == ["fetch", "layout", "extract", "gate", "embed", "store", "complete"]
    and events[-1]["held"], f"{time.time() - t:.1f}s")
d, s = chat("What is 18 Larkspur Ln worth now?")
rec("after parse: needs appraiser, cites new doc",
    d["valuation"]["gate_result"] == "appraiser" and "DOC-INS-001640" in d["answer"], f"{s:.1f}s")

rec("final reset", post("/api/demo/reset", {}) == 303)
rec("clean after reset", get("/review")[1].decode().count('class="cl-card review-item"') == 1)
print(f"\n{sum(c for _, c in results)} of {len(results)} checks passed")
