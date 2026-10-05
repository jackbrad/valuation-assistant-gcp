"""FastAPI Web Application for Appraisal-Grade Valuation AI.

Exposes:
- /ask: Valuation query, evidence panel, and citation viewer
- /review: Governance review queue with two-approver enforcement and stake blocking
- /cascade: 'What Changed' cascade revaluation inspector
- /health: Circuit breaker and model health monitor
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.state import state, ReviewItem
from app.users import USERS, name as _person_name
from config.loader import settings

app = FastAPI(title="Appraisal-Grade Valuation AI")

# Mount templates, static, and clearline design system
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
CLEARLINE_DIR = Path(__file__).resolve().parent.parent / "clearline"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["get_pending_queue_count"] = lambda: len([i for i in state.review_queue if i.status == "pending"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/clearline", StaticFiles(directory=str(CLEARLINE_DIR)), name="clearline")

def _fmt(v: Any) -> str:
    try:
        return f"{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def _person(uid: str) -> str:
    return _person_name(uid)


def _field_label(field: str) -> str:
    from app.explain import FEATURES
    return FEATURES.get(field, (field, ""))[0]


def _cites(evidence: str):
    from app.explain import _cites as parse
    return parse(evidence)


templates.env.globals.update(
    fmt=_fmt,
    person=_person,
    people=lambda uids: " and ".join(_person(u) for u in uids),
    field_label=_field_label,
    cites=_cites,
)



@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "val-valuation-app"}


@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse(request=request, name="chat.html", context={"agent_model": settings["models"]["gemini_agent"]})


class ChatIn(BaseModel):
    message: str
    history: List[Dict[str, str]] = []  # earlier turns, kept by the browser


_agents: Dict[str, Any] = {}
CHAT_CACHE = Path(__file__).resolve().parent.parent / "data_gen/out/chat_cache"


def _ask_with_fallback(message: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """Asks the primary agent model, retrying 429s, then falls back to a second model and region."""
    import time
    from agent.appraisal_agent import AppraisalAgent

    fallback = settings["models"].get("gemini_agent_fallback", {})
    attempts = [("primary", 0), ("primary", 2), ("fallback", 0), ("fallback", 4)]
    last_error: Optional[Exception] = None
    for key, wait in attempts:
        time.sleep(wait)
        try:
            if key not in _agents:
                _agents[key] = AppraisalAgent() if key == "primary" else AppraisalAgent(
                    location=fallback.get("location"), model=fallback.get("model"))
            return _agents[key].ask(message, history)
        except Exception as e:  # 429 quota, transient 5xx
            print(f"[!] Agent call failed on the {key} model: {e}")
            last_error = e
    raise last_error


def _cache_path(body: "ChatIn") -> Path:
    """One saved answer per conversation so far (earlier questions + this one)."""
    import hashlib
    key = " | ".join([t.get("text", "") for t in body.history if t.get("role") == "user"] + [body.message])
    return CHAT_CACHE / (hashlib.sha256(key.strip().lower().encode()).hexdigest()[:16] + ".json")


def _tool_output(steps: List[Dict[str, Any]], tool: str) -> Optional[Dict[str, Any]]:
    """Returns the last output of a tool from the agent trace (SDK wraps it in {'result': ...})."""
    for step in reversed(steps):
        if step["tool"] == tool and step.get("output"):
            out = step["output"]
            return out.get("result", out) if isinstance(out, dict) else None
    return None


@app.post("/api/chat")
async def api_chat(body: ChatIn):
    """Runs the Gemini agent for one turn. Panels are built only from this turn's tool
    outputs; a panel is null when this turn didn't touch it, so the page keeps the old one."""
    import json
    from datetime import datetime
    from fastapi.concurrency import run_in_threadpool
    from app import explain

    try:
        result = await run_in_threadpool(_ask_with_fallback, body.message, body.history)
    except Exception as e:
        # DEMO-SHORTCUT: replay the last successful answer to the same conversation, clearly labelled.
        cached = _cache_path(body)
        if cached.exists():
            replay = json.loads(cached.read_text())
            replay["replayed"] = {"saved_at": replay.get("saved_at"), "error": str(e)[:200]}
            return replay
        raise HTTPException(status_code=503, detail=f"Gemini is unavailable right now: {str(e)[:200]}")

    steps = result["steps"]
    search = _tool_output(steps, "search_documents")
    valuation = _tool_output(steps, "run_valuation")
    valuation = valuation if valuation and "error" not in valuation else None
    prop = _tool_output(steps, "resolve_property")
    prop = prop if prop and "error" not in prop else None

    # Which property this turn was about: resolved, valued, or searched.
    property_id = (prop or {}).get("property_id") or (valuation or {}).get("property_id")
    if not property_id:
        property_id = next((s["args"].get("property_id") for s in steps if s.get("args", {}).get("property_id")), None)
    if property_id and not prop and property_id in state.properties:
        prop = {"property_id": property_id, "address": state.properties[property_id]["address_line"]}

    response = {
        **result,
        "property": prop,
        "valuation": valuation,
        "documents": explain.documents_on_file(property_id, (search or {}).get("results", []))
                     if property_id and (search is not None or valuation is not None) else None,
        "issues": explain.issues(property_id, valuation) if valuation else None,
        "calculation": explain.calculation(valuation["valuation_id"]) if valuation else None,
    }
    response["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    CHAT_CACHE.mkdir(parents=True, exist_ok=True)
    _cache_path(body).write_text(json.dumps(response, default=str))
    return response


@app.get("/ask", response_class=HTMLResponse)
async def ask_page(
    request: Request,
    q: Optional[str] = "14 Larkspur Ln",
    user: str = "alex.reviewer"
):
    current_user = USERS.get(user, USERS["alex.reviewer"])
    valuation_result = None
    resolved_property = None
    evidence_notes = []

    # Check if catalog view requested
    if request.query_params.get("view") == "catalog":
        q = ""
    elif not q or not q.strip():
        q = "14 Larkspur Ln"

    if q:
        query_lower = q.lower()
        target_id = None
        if "14 larkspur" in query_lower:
            target_id = "P-000014"
        elif "18 larkspur" in query_lower:
            target_id = "P-000018"
        elif "22 hilltop" in query_lower:
            target_id = "P-000022"
        elif "7 wren" in query_lower:
            target_id = "P-000007"
        elif "31 mill race" in query_lower:
            target_id = "P-000031"
        else:
            # Search by street or id
            for pid, p in state.properties.items():
                if p["address_line"].lower() in query_lower or pid.lower() in query_lower:
                    target_id = pid
                    break

        if target_id and target_id in state.properties:
            resolved_property = state.properties[target_id]
            valuation_result = state.run_valuation_for_property(target_id)
            evidence_notes = state.get_evidence_notes(target_id)

    agent_response = None
    if q and ("?" in q or "worth" in q.lower() or "what" in q.lower() or "how much" in q.lower() or "refi" in q.lower()):
        try:
            from agent.appraisal_agent import AppraisalAgent
            agent = AppraisalAgent()
            agent_res = agent.ask(q)
            agent_response = agent_res.get("answer")
        except Exception as e:
            print(f"[!] Agent error: {e}")

    return templates.TemplateResponse(
        request=request,
        name="ask.html",
        context={
            "q": q or "",
            "user": user,
            "current_user": current_user,
            "users": USERS,
            "property": resolved_property,
            "valuation": valuation_result,
            "evidence_notes": evidence_notes,
            "agent_response": agent_response,
            "cascade_runs": state.cascade_runs,
            "portfolio_properties": list(state.properties.values()),
            "prop_map": {
                (p.get("property_id") if isinstance(p, dict) else getattr(p, "property_id", "")): (
                    p.get("address_line") if isinstance(p, dict) else getattr(p, "address_line", "")
                )
                for p in state.properties.values()
            },
        },
    )


@app.get("/api/agent/ask")
@app.post("/api/agent/ask")
async def api_agent_ask(q: str):
    from agent.appraisal_agent import AppraisalAgent
    agent = AppraisalAgent()
    return agent.ask(q)


@app.post("/api/flags")
async def submit_flag(
    property_id: str = Form(...),
    field_name: str = Form(...),
    proposed_value: str = Form(...),
    reason: str = Form(...),
    evidence_desc: str = Form(...),
    user_id: str = Form("alex.reviewer"),
):
    prop = state.properties.get(property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    item_id = f"REV-{len(state.review_queue) + 1:06d}"
    is_value_moving = field_name in settings.get("feedback", {}).get("value_moving_fields", [])

    new_item = ReviewItem(
        item_id=item_id,
        target_type="fact",
        property_id=property_id,
        property_address=prop["address_line"],
        field_name=field_name,
        current_value=prop.get(field_name),
        proposed_value=proposed_value,
        reason=reason,
        evidence_desc=evidence_desc,
        evidence_uri=None,
        flagger_id=user_id,
        route="steward" if "stale" in reason.lower() else "appraiser",
        requires_two_approvals=is_value_moving,
        status="pending",
    )
    state.review_queue.insert(0, new_item)
    return RedirectResponse(url=f"/review?user={user_id}", status_code=303)


@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request, user: str = "alex.reviewer"):
    current_user = USERS.get(user, USERS["alex.reviewer"])
    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "user": user,
            "current_user": current_user,
            "users": USERS,
            "queue": state.review_queue,
            "corrections": state.corrections,
        },
    )


@app.post("/api/review/{item_id}/approve")
async def approve_item(item_id: str, user_id: str = Form(...)):
    user_info = USERS.get(user_id)
    if not user_info:
        raise HTTPException(status_code=400, detail="Unknown user")

    item = next((i for i in state.review_queue if i.item_id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")

    # 1. Stake check
    if user_info["has_stake"]:
        raise HTTPException(
            status_code=403,
            detail=f"User {user_id} has a financial stake in this transaction and cannot approve value-moving modifications."
        )

    # 2. Flagger check
    if user_id == item.flagger_id:
        raise HTTPException(
            status_code=403,
            detail="The submitting flagger cannot also act as the approving reviewer."
        )

    # 3. Duplicate check
    if user_id in item.approvals:
        raise HTTPException(
            status_code=400,
            detail="This user has already approved this item."
        )

    item.approvals.append(user_id)

    # Check if complete
    if not item.requires_two_approvals or len(item.approvals) >= 2:
        state.apply_correction(item_id, user_id)

    return RedirectResponse(url=f"/review?user={user_id}", status_code=303)


@app.post("/api/demo/reset")
async def demo_reset():
    """Restores the seeded starting state (no flags or corrections) in this process."""
    from fastapi.concurrency import run_in_threadpool
    from pipeline.ingest import remove_arrivals

    def reset():
        remove_arrivals()  # documents parsed live during the demo go back to "not parsed yet"
        state.__init__()

    await run_in_threadpool(reset)
    return RedirectResponse(url="/review", status_code=303)


@app.post("/api/ingest/{doc_id}")
async def ingest(doc_id: str):
    """Parses one landed document live and streams each pipeline step as a line of JSON."""
    import json
    from fastapi.responses import StreamingResponse
    from pipeline.ingest import ARRIVALS, ingest_document

    if doc_id not in ARRIVALS:
        raise HTTPException(status_code=400, detail=f"{doc_id} isn't available for live ingestion in this demo.")

    def events():
        try:
            for event in ingest_document(doc_id):
                yield json.dumps(event, default=str) + "\n"
        except Exception as e:
            yield json.dumps({"step": "error", "status": "error", "detail": str(e)[:300]}) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.get("/cascade", response_class=HTMLResponse)
async def cascade_page(request: Request, user: str = "alex.reviewer"):
    current_user = USERS.get(user, USERS["alex.reviewer"])
    return templates.TemplateResponse(
        request=request,
        name="cascade.html",
        context={
            "user": user,
            "current_user": current_user,
            "users": USERS,
            "cascade_runs": state.cascade_runs,
        },
    )


@app.get("/health", response_class=HTMLResponse)
async def health_page(request: Request, user: str = "alex.reviewer"):
    current_user = USERS.get(user, USERS["alex.reviewer"])
    return templates.TemplateResponse(
        request=request,
        name="health.html",
        context={
            "user": user,
            "current_user": current_user,
            "users": USERS,
            "breaker_state": state.breaker_state,
            "limit": settings.get("breaker", {}).get("mdape_abs_threshold", 0.08),
            "g2": settings.get("g2", {}),
        },
    )
