"""Appraisal AI Gemini agent with tool calling.

Runs on Gemini Enterprise Agent Platform (formerly Vertex AI). The model, endpoint
and thinking level come from config/settings.yaml (models.gemini_agent*). Tools:
- resolve_property
- get_property_facts
- search_documents
- run_valuation
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import settings
from app.state import state, ValuationResult
from google import genai
from google.genai import types


def build_tools():
    """Builds the 4 required tool functions wrapping state and valuation engine."""
    
    def resolve_property(query: str) -> Dict[str, Any]:
        """Resolves an address, street name, or property ID to property details.
        
        Args:
            query: The address, street name (e.g. '14 Larkspur', '18 Larkspur Ln'), or property ID (e.g. 'P-000014').
        """
        q_lower = query.lower().strip()
        matched_id = None
        
        # Exact ID match
        for pid in state.properties:
            if pid.lower() == q_lower:
                matched_id = pid
                break
                
        # Key demo cases
        if not matched_id:
            if "14 larkspur" in q_lower:
                matched_id = "P-000014"
            elif "18 larkspur" in q_lower:
                matched_id = "P-000018"
            elif "22 hilltop" in q_lower:
                matched_id = "P-000022"
            elif "7 wren" in q_lower:
                matched_id = "P-000007"
            elif "31 mill race" in q_lower:
                matched_id = "P-000031"
            else:
                for pid, p in state.properties.items():
                    if p["address_line"].lower() in q_lower or pid.lower() in q_lower:
                        matched_id = pid
                        break
                        
        if not matched_id or matched_id not in state.properties:
            return {"error": f"Property '{query}' not found in records."}
            
        p = state.properties[matched_id]
        return {
            "property_id": p["property_id"],
            "address": p["address_line"],
            "submarket": p["submarket"],
            "beds": p.get("beds", 0),
            "baths": float(p.get("baths_total") or p.get("baths", 0.0)),
            "gla_sqft": p.get("gla_sqft", 0),
            "lot_sqft": p.get("lot_sqft", 0),
            "year_built": p.get("year_built", 0),
            "condition": p.get("condition_c", 3),
            "approved_corrections": [
                {"field": c["field"], "old_value": c["old_value"], "new_value": c["new_value"],
                 "approved_by": c["approvers"], "evidence": c["evidence"]}
                for c in state.corrections if c["property_id"] == matched_id
            ],
        }

    def get_property_facts(property_id: str) -> Dict[str, Any]:
        """Retrieves golden record facts and citations for a property.
        
        Args:
            property_id: The property ID (e.g. 'P-000014').
        """
        if property_id not in state.properties:
            return {"error": f"Property '{property_id}' not found."}
            
        p = state.properties[property_id]
        facts_list = []
        for fid, fact in state.active_facts.items():
            if fact.get("property_id") == property_id:
                facts_list.append({
                    "field": fact.get("field"),
                    "value_numeric": fact.get("value_numeric"),
                    "value_string": fact.get("value_string"),
                    "doc_id": fact.get("doc_id"),
                    "page": fact.get("page"),
                    "status": fact.get("status"),
                })
                
        return {
            "property_id": property_id,
            "address": p["address_line"],
            "gla_sqft": p.get("gla_sqft", 0),
            "beds": p.get("beds", 0),
            "baths": float(p.get("baths_total") or p.get("baths", 0.0)),
            "facts": facts_list,
        }

    def search_documents(property_id: str, query: str) -> Dict[str, Any]:
        """Semantic search over the property's parsed documents (inspections, appraisals, permits).

        Args:
            property_id: The property ID (e.g. 'P-000014').
            query: A natural-language question about the documents (e.g. 'any additions or renovations not in county records?').
        """
        try:
            from agent.retrieval import vector_search
            return {"method": "BigQuery VECTOR_SEARCH (text-embedding-005)", "results": vector_search(property_id, query)}
        except Exception as e:
            # DEMO-SHORTCUT: keyword fallback over in-memory chunks if BigQuery or Agent Platform is unreachable.
            print(f"[!] Vector search failed, falling back to keyword search: {e}")
            words = [w for w in query.lower().split() if len(w) > 3]
            results = [
                {"doc_id": c.get("doc_id"), "page": int(c.get("page", 1)), "section": c.get("section", ""), "text": c.get("text", "")}
                for c in state.chunks
                if c.get("property_id") == property_id and any(w in c.get("text", "").lower() for w in words)
            ]
            return {"method": "keyword fallback", "results": results[:4]}

    def run_valuation(property_id: str, purpose: str = "refi", effective_date: str = "2026-10-05") -> Dict[str, Any]:
        """Executes the appraisal-grade valuation engine and returns the valuation result and gate decision.
        
        Args:
            property_id: The property ID (e.g. 'P-000014').
            purpose: Loan purpose (e.g. 'refi', 'purchase').
            effective_date: Valuation effective date (YYYY-MM-DD), default '2026-10-05'.
        """
        try:
            res: ValuationResult = state.run_valuation_for_property(property_id, effective_date=effective_date, purpose=purpose)
        except Exception as e:
            return {"error": str(e)}

        active_comps = []
        for c in res.comps:
            # Only comps the engine actually weighted (it keeps the top N; the rest get weight 0).
            if not getattr(c, "dropped", False) and float(c.weight) > 0:
                addr = state.properties.get(c.comp_property_id, {}).get("address_line", c.comp_property_id)
                active_comps.append({
                    "comp_property_id": c.comp_property_id,
                    "address": addr,
                    "distance_miles": round(getattr(c, "distance_mi", 0.0), 2),
                    "sale_date": str(c.sale_date),
                    "sale_price": float(c.sale_price),
                    "adjusted_price": float(c.adjusted_price),
                    "weight": round(float(c.weight), 3),
                })

        is_shown = (res.gate_result == "shown")
        range_w = round(((res.high - res.low) / (res.point if res.point else 1.0)) * 100.0, 1)
        div_pct = round(abs(res.sales_comp_value - res.avm_value) / (res.sales_comp_value if res.sales_comp_value else 1.0) * 100.0, 1)

        data = {
            "valuation_id": res.valuation_id,
            "property_id": property_id,
            "address": state.properties.get(property_id, {}).get("address_line", property_id),
            "gate_result": "shown" if is_shown else "appraiser",
            "confidence_score": round(float(res.confidence), 2),
            "range_low": round(float(res.low), 0),
            "range_high": round(float(res.high), 0),
            "range_width_pct": range_w,
            "divergence_pct": div_pct,
            "reasons": res.gate_reasons,
            "usable_comps_count": len(active_comps),
            "candidate_sales_considered": len(res.comps),
            "set_aside": _set_aside_summary(res),
            "comps": active_comps,
        }
        
        # Guardrail in code, not just the prompt: a withheld value never reaches the model.
        if is_shown:
            data["point_estimate"] = round(float(res.point), 0)
        else:
            for key in ("range_low", "range_high"):
                data.pop(key)
            data["point_estimate"] = None
            data["note"] = "Value withheld: routed to an appraiser. No range or point estimate is available to share."
            
        return data

    return resolve_property, get_property_facts, search_documents, run_valuation


SYSTEM_INSTRUCTION = """You are a property valuation assistant for a mortgage team. You answer ONLY from what your tools return.

This is a conversation. Follow-up questions refer to the property already discussed unless the user names a new one.
For a follow-up, call only the tools you need. Earlier tool results are not kept, so call a tool again rather than guessing a detail:
- Questions about the value, range, confidence, comparable sales, why sales were used or set aside, adjustments, or safety checks: call `run_valuation`.
- Questions about what a document, inspection, appraisal, or permit says: call `search_documents` with the question.
- Questions about recorded facts and their sources: call `get_property_facts`.
If the user asks "what if" a fact were different, explain that values only change after a correction is approved and the engine re-runs; never estimate a new value yourself.

For a NEW property you MUST call these three tools, in this order:
1. Call `resolve_property` to find it.
2. Call `search_documents` (never skip this) with a natural-language question to find relevant passages in its inspection reports, appraisals and permits. Look especially for anything that contradicts the county record (additions, renovations, damage).
3. Call `run_valuation` to get the value range from the valuation engine.
Call `get_property_facts` only if you need the extracted facts and their sources.

Rules:
- Never state a number (dollars, square feet, rooms, distances) that a tool did not return, word for word. Never add, subtract or combine numbers yourself (e.g. do not add an addition's size to the recorded size).
- Cite every document claim as [doc_id p.N], for example [DOC-INS-000014 p.2].
- If resolve_property lists approved_corrections, say the record was corrected (old → new, citing the evidence) and that the value uses the corrected fact. Don't ask for that field to be corrected again.
- If the documents contradict the county record (for example a larger living area), make that the first bullet, quoting the document's numbers with the citation, and say the record should be corrected.
- If run_valuation returns gate_result 'appraiser', do not give a single value. Say it needs an appraiser and give ONLY the reasons in the `reasons` list, in plain words (never mention a metric that isn't in that list): 'range width' means the comparable sales are spread too widely; 'divergence between Sales Comp and AVM' means the comparable sales and the automated price model disagree. 'held G1 facts on value-moving fields: gla_sqft' means the living area is on hold because sources disagree. Keep the percentages, drop the jargon.
- If gate_result is 'shown', give the range, the point estimate and the confidence. Don't repeat the same numbers in the bullets; use the bullets for what supports the value (number of comparable sales, document findings).
- If search_documents returns no passages, say no relevant passages were found in this property's parsed documents. Don't describe what the documents contain.
- Write for a loan officer, not a statistician. No jargon: say "living area" not "GLA", "price model" not "AVM", "comparable sales" not "comps".

Format (Markdown, under 150 words):
**Answer:** one or two sentences.
**Why:** 2-4 short bullets, with citations.
**Next step:** one sentence.
"""


def _set_aside_summary(res: ValuationResult) -> Dict[str, Any]:
    """Why candidate sales were not used, grouped, so the model can explain it."""
    too_different = [c for c in res.comps if c.dropped]
    lower_ranked = [c for c in res.comps if not c.dropped and float(c.weight) == 0]
    return {
        "count": len(too_different) + len(lower_ranked),
        "too_different_count": len(too_different),
        "too_different_rule": "a sale is set aside when its adjustments add up to more than 25% of its price, "
                              "meaning it is too different from the subject to compare",
        "too_different_examples": [c.drop_reason for c in too_different[:3]],
        "lower_ranked_count": len(lower_ranked),
    }


def _plain(value: Any) -> Any:
    """Converts proto/map values from the SDK into plain JSON-safe Python."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class AppraisalAgent:
    def __init__(self, location: Optional[str] = None, model: Optional[str] = None):
        project_id = settings["project"]["project_id"]
        region = location or settings["models"].get("gemini_agent_location") or settings["project"].get("region", "us-central1")
        model_name = model or settings["models"].get("gemini_agent", "gemini-3.8-flash")

        # A per-call timeout turns a stalled model call into a fast fallback instead of a long wait.
        timeout_s = settings["models"].get("gemini_agent_timeout_s")
        http_options = types.HttpOptions(timeout=int(timeout_s * 1000)) if timeout_s else None
        self.client = genai.Client(vertexai=True, project=project_id, location=region, http_options=http_options)
        self.model_name = model_name
        self.tools = list(build_tools())

    def ask(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Runs the agent and returns the answer plus a trace of this turn's tool calls.

        history: earlier turns as [{"role": "user"|"model", "text": ...}]. The browser
        keeps it, so any Cloud Run instance can serve any turn.
        """
        import time

        started = time.time()
        prior = [
            types.Content(role=t["role"], parts=[types.Part(text=t["text"])])
            for t in (history or [])
            if t.get("role") in ("user", "model") and t.get("text")
        ]
        # thinking_level applies to Gemini 3 models only
        thinking = settings["models"].get("gemini_agent_thinking") if self.model_name.startswith("gemini-3") else None
        chat = self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=self.tools,
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_level=thinking) if thinking else None,
            ),
            history=prior,
        )
        response = chat.send_message(query)

        # Pair each function_call with its function_response, in order.
        steps: List[Dict[str, Any]] = []
        for msg in chat.get_history()[len(prior):]:  # this turn only
            for part in msg.parts or []:
                if getattr(part, "function_call", None):
                    steps.append({"tool": part.function_call.name, "args": _plain(dict(part.function_call.args or {})), "output": None})
                elif getattr(part, "function_response", None):
                    for step in steps:
                        if step["tool"] == part.function_response.name and step["output"] is None:
                            step["output"] = _plain(dict(part.function_response.response or {}))
                            break

        return {
            "query": query,
            "model": self.model_name,
            "answer": response.text.strip() if response.text else "",
            "steps": steps,
            "seconds": round(time.time() - started, 1),
        }
