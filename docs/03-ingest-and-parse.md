# 03 — Ingest, parse, clean, G1

Reference SQL: `sql/02_remote_models.sql`, `sql/03_parse_and_extract.sql`.

## Landing

- Generator uploads to `gs://<proj>-landing/<source_system>/<doc_type>/<doc_id>.pdf`.
- A manifest (`gs://<proj>-landing/_manifest.jsonl`) carries `doc_id, property_hint (address string), doc_type, source_system, effective_date`. Real silos rarely have clean keys, so **do not** put `property_id` in the manifest; resolution must happen in the pipeline.
- Object table `val_raw.landed_pdfs` over `gs://<proj>-landing/*` (connection `US.vertex`, `object_metadata = 'SIMPLE'`, metadata caching on with manual refresh).

## Parse (step 1: Document AI)

- Remote model `val_raw.layout_parser` → Document AI Layout Parser processor.
- `ML.PROCESS_DOCUMENT` over the object table → `val_raw.parsed_docai` (keep the full JSON).
- Python glue (`pipeline/docai_to_fields.py`) walks layout blocks and tables and emits candidate field values with `page`, `bbox`, `confidence` into `val_raw.field_candidates`. Use label maps per `doc_type` (e.g. appraisal grid row "GLA" / "Gross Living Area" / "Above Grade Living Area" → `gla_sqft`).
- Narrative blocks (inspection findings, appraiser comments, disclosure explanations) → `val_raw.text_blocks`.

## Parse (step 2: Gemini, only where needed)

Send a page to Gemini when any of:
- page is image-only (no text layer) or Doc AI confidence < `parse.docai_min_confidence`;
- `doc_type = 'disclosure'` (checkboxes);
- a required field for that `doc_type` is missing after step 1;
- a table spans pages (detected by a header row with no totals on the last page).

Call via `AI.GENERATE` with an `output_schema` per doc type (see `sql/03`). Cache by `sha256(page_image || prompt_version)` in `val_raw.gemini_cache`. Each returned field gets `extractor='gemini'` and the model's self-reported confidence clipped to `parse.gemini_confidence_cap` (default 0.9). Ask Gemini to return the page-relative bbox or quote the source text for each field; store it.

## Clean and resolve

`pipeline/clean_resolve.py` + `sql/03` cleaning section:
1. Normalize units (`2,080 sq. ft.` → 2080; acres → sq ft; "1.5 baths" → full 1 / half 1).
2. Normalize enums (condition "C3" / "Average" → 3).
3. **Entity resolution** of `property_hint` → `property_id`: standardize address (USPS-style suffixes, unit numbers), exact match on normalized address; fall back to APN found in document text; fall back to Jaro-Winkler ≥ 0.92 on address within the same ZIP. Unresolved docs → review item (`route='steward'`).
4. **Legacy → UAD 3.6 mapping**: legacy form labels map to UAD 3.6-style field names (table `val_core.field_map`).
5. Write candidates to `val_core.facts` with `status` decided by G1.

## G1 — data gate (`sql/03` G1 section)

A candidate fact is **held** (status `held`, review item created) if any:
- `confidence < g1.min_confidence` (default 0.80);
- out of range (`gla_sqft` 300–15000, `beds` 0–12, `year_built` 1850–current, etc.; ranges in settings);
- **cross-source conflict**: another active fact for the same property+field from a different `doc_id` differs by more than tolerance (`gla_sqft` 5%, `lot_sqft` 5%, `year_built` ±1, integers exact, booleans exact). Both facts are held and one `adjudication` review item is created listing both citations.

Seeded demo case: `14 Larkspur Ln` — county record and the 2019 legacy appraisal say GLA 1,240; the 2025 inspection report describes a permitted 840 sq ft addition (narrative only, no new GLA field). Nothing conflicts numerically, so the wrong GLA (1,240) passes G1. That is the point: the human flag catches what the gate can't.

Held facts never enter `golden_record`. They are visible in the UI as "held for review" with citations.

## Chunks and embeddings

- Chunk `text_blocks` by section (≤ 1,200 chars, 150 overlap), keep `doc_id`, `page`, `section`.
- Remote embedding model `val_raw.embedder`; `ML.GENERATE_EMBEDDING` into `val_core.chunks.embedding`.
- Vector index on `chunks.embedding` only if the table exceeds the minimum row count for indexes; otherwise brute-force `VECTOR_SEARCH` is fine for the demo.

## Acceptance

- ≥ 95% of seeded fields extracted with correct value on clean PDFs; ≥ 85% on scanned variants (compare with generator ground truth in `val_raw.ground_truth`).
- Every active fact has `doc_id` and `page`.
- The seeded GLA conflict for `22 Hilltop Rd` (see docs/09) is held and appears in the review queue.
