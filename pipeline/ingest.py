"""Ingest one document end to end, reporting each step as it happens.

Same stages as the batch pipeline (pipeline/run_pipeline.py), for a single
document that has landed in Cloud Storage but hasn't been parsed:

  1. Fetch the PDF from the landing bucket
  2. Document AI Layout Parser -> sections and paragraphs with page numbers
  3. Gemini -> typed facts, each with its page and a source quote
  4. Data quality gate (G1): a fact that disagrees with the county record is
     held and sent to the review queue instead of being used
  5. text-embedding-005 vectors for each paragraph
  6. BigQuery load jobs into val_raw.text_blocks, val_core.facts, val_core.chunks

Used by the "Parse now" button (POST /api/ingest/{doc_id}).
"""
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List

from config.loader import settings
from pipeline.run_pipeline import build_extraction_prompt, extract_layout_blocks

PROJECT = settings["project"]["project_id"]
VALUE_MOVING = set(settings.get("feedback", {}).get("value_moving_fields", []))
DOC_LABELS = {"inspection": "inspection report", "appraisal_legacy": "prior appraisal", "permit": "building permit"}

# Documents the live demo may ingest (and that "Reset demo data" removes again).
ARRIVALS = {"DOC-INS-001640"}


def _rating(field: str, value: Any) -> str:
    """3.0 -> 'C3' for condition, 'Q3' for quality; plain number otherwise."""
    prefix = {"condition_c": "C", "quality_q": "Q"}.get(field, "")
    return f"{prefix}{float(value):g}"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _step(key: str, title: str, status: str, detail: str = "", started: float = 0.0, **extra) -> Dict[str, Any]:
    return {"step": key, "title": title, "status": status, "detail": detail,
            "seconds": round(time.time() - started, 1) if started else None, **extra}


def queue_conflict(state, fact: Dict[str, Any], record_value: Any, doc_type: str, uri: str = "") -> None:
    """Hold a fact that disagrees with the record and open a review item for it (G1)."""
    from app.state import ReviewItem

    pid, field = fact["property_id"], fact["field"]
    if field not in state.held_facts.setdefault(pid, []):
        state.held_facts[pid].append(field)
    if any(i.property_id == pid and i.field_name == field and i.status == "pending" for i in state.review_queue):
        return
    state.review_queue.insert(0, ReviewItem(
        item_id=f"REV-{len(state.review_queue) + 1:06d}",
        target_type="fact",
        property_id=pid,
        property_address=state.properties[pid]["address_line"],
        field_name=field,
        current_value=record_value,
        proposed_value=fact["value_numeric"],
        reason=f"Cross-source conflict: county record {_rating(field, record_value)} vs "
               f"{DOC_LABELS.get(doc_type, doc_type)} {_rating(field, fact['value_numeric'])}",
        evidence_desc=f"{fact['doc_id']} p.{fact['page']}",
        evidence_uri=uri,
        flagger_id="pipeline_g1",
        route="adjudication",
        requires_two_approvals=field in VALUE_MOVING,
        status="pending",
    ))


def ingest_document(doc_id: str) -> Iterator[Dict[str, Any]]:
    """Runs every stage for one document, yielding a progress event per stage."""
    from google.cloud import bigquery, documentai_v1 as documentai, storage
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from vertexai.language_models import TextEmbeddingModel

    from app.explain import _manifest
    from app.state import state

    meta = next((d for docs in _manifest().values() for d in docs if d["doc_id"] == doc_id), None)
    if not meta:
        yield _step("fetch", "Fetch from Cloud Storage", "error", f"{doc_id} isn't in the document manifest.")
        return
    pid, doc_type, uri = meta["property_id"], meta["doc_type"], meta["uri"]
    record = state.properties[pid]
    now_ts = datetime.now(timezone.utc).isoformat()

    # 1. Fetch
    t = time.time()
    yield _step("fetch", "Fetch from Cloud Storage", "running", uri)
    bucket, _, blob = uri.removeprefix("gs://").partition("/")
    pdf_bytes = storage.Client(project=PROJECT).bucket(bucket).blob(blob).download_as_bytes()
    yield _step("fetch", "Fetch from Cloud Storage", "done", f"{len(pdf_bytes) / 1024:.1f} KB from {uri}", t)

    # 2. Layout
    t = time.time()
    yield _step("layout", "Document AI layout parsing", "running", "Layout Parser processor")
    docai_loc = settings["project"]["docai_location"]
    docai = documentai.DocumentProcessorServiceClient(client_options={"api_endpoint": f"{docai_loc}-documentai.googleapis.com"})
    processor = f"projects/281362663093/locations/{docai_loc}/processors/c745df858c6e37e0"
    result = docai.process_document(request=documentai.ProcessRequest(
        name=processor, raw_document=documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")))
    blocks = extract_layout_blocks(result.document)
    pages = sorted({b["page"] for b in blocks})
    yield _step("layout", "Document AI layout parsing", "done",
                f"{len(blocks)} blocks across {len(pages)} pages, each with its section and page number", t)

    # 3. Extract facts
    t = time.time()
    yield _step("extract", "Gemini fact extraction", "running", settings["models"]["gemini_extract"])
    vertexai.init(project=PROJECT, location=settings["project"]["region"])
    model = GenerativeModel(settings["models"]["gemini_extract"])
    full_text = "\n\n".join(f"[Page {b['page']}] {b['text']}" for b in blocks)
    raw_facts: List[Dict[str, Any]] = []
    for attempt in range(3):
        try:
            resp = model.generate_content(build_extraction_prompt(full_text),
                                          generation_config={"response_mime_type": "application/json", "temperature": 0})
            raw_facts = json.loads(resp.text).get("facts", [])
            break
        except Exception as e:  # 429s and the odd malformed JSON
            if attempt == 2:
                yield _step("extract", "Gemini fact extraction", "error", str(e)[:200], t)
                return
            time.sleep(2 * (attempt + 1))
    facts = []
    for ef in raw_facts:
        if not ef.get("field"):
            continue
        facts.append({
            "fact_id": f"FACT-{doc_id}-{ef['field']}",
            "property_id": pid,
            "field": ef["field"],
            "value_numeric": float(ef["value_numeric"]) if ef.get("value_numeric") is not None else None,
            "value_string": str(ef.get("value_string", "")),
            "unit": ef.get("unit"),
            "doc_id": doc_id,
            "page": int(ef.get("page") or 1),
            "bbox": json.dumps({"source_quote": ef.get("source_quote", "")}),
            "source_doc_type": doc_type,
            "extractor": settings["models"]["gemini_extract"],
            "confidence": 0.90,
            "status": "active",
            "hold_reasons": [],
            "valid_from": "2026-10-05",
            "recorded_at": now_ts,
            "retired_at": None,
            "superseded_by": None,
            "correction_id": None,
            "demo_run_id": "live-ingest",
        })
    yield _step("extract", "Gemini fact extraction", "done", _plural(len(facts), "typed fact"), t,
                facts=[{"field": f["field"], "value": f["value_string"], "page": f["page"]} for f in facts])

    # 4. Data quality gate (G1)
    t = time.time()
    held = []
    for f in facts:
        rec = record.get(f["field"])
        if f["field"] in VALUE_MOVING and f["value_numeric"] is not None and rec is not None \
                and abs(f["value_numeric"] - float(rec)) > 0.5:
            f["status"] = "held"
            f["hold_reasons"] = [f"County record {float(rec):g} vs document {f['value_numeric']:g}"]
            held.append({"field": f["field"], "record": _rating(f["field"], rec),
                         "document": _rating(f["field"], f["value_numeric"]), "page": f["page"]})
    yield _step("gate", "Data quality check", "done",
                f"{_plural(len(held), 'fact')} disagree{'s' if len(held) == 1 else ''} with the county record, "
                "so held for review instead of used" if held
                else "No conflicts with the county record", t, held=held)

    # 5. Embeddings
    t = time.time()
    yield _step("embed", "Embeddings", "running", settings["models"]["embedding"])
    chunks = [{
        "chunk_id": f"CHK-{doc_id}-{b['page']}-{i + 1:03d}", "doc_id": doc_id, "property_id": pid,
        "page": int(b["page"]), "section": b["section"], "text": b["text"],
    } for i, b in enumerate(blocks) if len(b["text"]) > 40]
    embedder = TextEmbeddingModel.from_pretrained(settings["models"]["embedding"])
    for i in range(0, len(chunks), 5):
        batch = chunks[i:i + 5]
        for c, e in zip(batch, embedder.get_embeddings([c["text"][:1000] for c in batch])):
            c.update(embedding=[float(v) for v in e.values], pii_findings=0, created_at=now_ts)
    yield _step("embed", "Embeddings", "done", f"{len(chunks)} paragraphs embedded (768 dimensions)", t)

    # 6. BigQuery (load jobs, not streaming, so a rehearsal reset can delete the rows)
    t = time.time()
    yield _step("store", "Write to BigQuery", "running", "val_raw.text_blocks, val_core.facts, val_core.chunks")
    bq = bigquery.Client(project=PROJECT, location=settings["project"]["bq_location"])
    text_blocks = [{"block_id": f"BLK-{doc_id}-{b['page']}-{i + 1:03d}", "doc_id": doc_id, "page": int(b["page"]),
                    "section": b["section"], "text": b["text"], "extractor": "docai_layout_parser", "created_at": now_ts}
                   for i, b in enumerate(blocks)]

    def replace_rows(table: str, rows: List[Dict[str, Any]]) -> None:
        bq.query(f"DELETE FROM `{PROJECT}.{table}` WHERE doc_id = @d", job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("d", "STRING", doc_id)])).result()
        if rows:
            bq.load_table_from_json(rows, f"{PROJECT}.{table}", job_config=bigquery.LoadJobConfig(
                write_disposition="WRITE_APPEND")).result()

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:  # the three tables are independent
        list(pool.map(lambda tr: replace_rows(*tr), [
            ("val_raw.text_blocks", text_blocks), ("val_core.facts", facts), ("val_core.chunks", chunks)]))
    yield _step("store", "Write to BigQuery", "done",
                f"{_plural(len(text_blocks), 'block')}, {_plural(len(facts), 'fact')}, "
                f"{_plural(len(chunks), 'searchable chunk')}", t)

    # Make the running app see it straight away.
    state.chunks = [c for c in state.chunks if c.get("doc_id") != doc_id] + [
        {k: c[k] for k in ("chunk_id", "doc_id", "property_id", "page", "section", "text")} for c in chunks]
    for f in facts:
        state.active_facts[f["fact_id"]] = f
        if f["status"] == "held":
            queue_conflict(state, f, record.get(f["field"]), doc_type, uri)

    yield {"step": "complete", "status": "done", "property_id": pid, "address": record["address_line"],
           "held": held, "doc_id": doc_id}


def remove_arrivals(bq=None) -> None:
    """Deletes ingested demo arrivals from BigQuery so the demo can be rehearsed again."""
    from google.cloud import bigquery
    bq = bq or bigquery.Client(project=PROJECT, location=settings["project"]["bq_location"])
    for table in ("val_raw.text_blocks", "val_core.facts", "val_core.chunks"):
        bq.query(f"DELETE FROM `{PROJECT}.{table}` WHERE doc_id IN UNNEST(@ids)", job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", sorted(ARRIVALS))])).result()
