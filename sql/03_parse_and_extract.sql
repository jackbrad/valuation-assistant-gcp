-- 03 — Parse, extract, clean, G1, chunks
-- Reference SQL: Python glue in pipeline/ handles Doc AI JSON walking and address resolution.
-- VERIFY ML.PROCESS_DOCUMENT output columns and AI.GENERATE signature against current docs.

-- 3.1 Parse every landed PDF with Document AI Layout Parser (incremental: skip parsed URIs)
CREATE TABLE IF NOT EXISTS `${PROJECT}.val_raw.parsed_docai` AS
SELECT * FROM ML.PROCESS_DOCUMENT(
  MODEL `${PROJECT}.val_raw.layout_parser`,
  TABLE `${PROJECT}.val_raw.landed_pdfs`
) LIMIT 0;

INSERT INTO `${PROJECT}.val_raw.parsed_docai`
SELECT * FROM ML.PROCESS_DOCUMENT(
  MODEL `${PROJECT}.val_raw.layout_parser`,
  (SELECT * FROM `${PROJECT}.val_raw.landed_pdfs`
   WHERE uri NOT IN (SELECT uri FROM `${PROJECT}.val_raw.parsed_docai`))
);
-- pipeline/docai_to_fields.py then writes val_raw.field_candidates (extractor='docai')
-- and val_raw.text_blocks from the parsed JSON.

-- 3.2 Hard pages → Gemini with a typed schema (example: legacy appraisal subject section)
-- pipeline/select_hard_pages.py writes val_raw.hard_pages(doc_id, page, uri, doc_type, reason, page_ref)
-- where page_ref is an ObjectRef to a single-page PDF/PNG produced for that page.
INSERT INTO `${PROJECT}.val_raw.gemini_cache` (cache_key, doc_id, page, response, created_at)
SELECT
  TO_HEX(SHA256(CONCAT(h.uri, ':', CAST(h.page AS STRING), ':${PROMPT_VERSION}'))),
  h.doc_id, h.page,
  TO_JSON(AI.GENERATE(
    ('You extract fields from one page of a residential appraisal. ',
     'Return only values printed on the page. For each field also return the exact source text. ',
     'If a field is absent, return null. ', h.page_ref),
    connection_id => '${PROJECT}.${BQ_LOCATION}.vertex',
    endpoint => '${GEMINI_EXTRACT_MODEL}',
    output_schema => 'gla_sqft INT64, gla_source_text STRING, beds INT64, baths_full INT64, baths_half INT64, year_built INT64, lot_sqft INT64, condition_c STRING, quality_q STRING, address STRING, apn STRING, confidence FLOAT64'
  )),
  CURRENT_TIMESTAMP()
FROM `${PROJECT}.val_raw.hard_pages` h
WHERE h.doc_type IN ('appraisal_legacy')
  AND TO_HEX(SHA256(CONCAT(h.uri, ':', CAST(h.page AS STRING), ':${PROMPT_VERSION}')))
      NOT IN (SELECT cache_key FROM `${PROJECT}.val_raw.gemini_cache`);
-- Repeat with a disclosure schema (checkbox booleans) and an inspection schema
-- (condition_c, roof_age_yrs, foundation_issue, additions[]: {year, sqft, permit}).

-- 3.3 G1: cross-source conflicts on candidate facts (run after resolve → staged facts)
-- val_core.facts_staged has the same columns as facts, status NULL.
CREATE OR REPLACE TEMP TABLE g1_conflicts AS
SELECT a.fact_id, ARRAY_AGG(DISTINCT b.fact_id) AS conflicting_fact_ids
FROM `${PROJECT}.val_core.facts_staged` a
JOIN (
  SELECT * FROM `${PROJECT}.val_core.facts_staged`
  UNION ALL
  SELECT * EXCEPT(status, hold_reasons, retired_at, superseded_by, correction_id, demo_run_id),
         NULL, NULL, NULL, NULL, NULL, NULL
  FROM `${PROJECT}.val_core.facts` WHERE status = 'active' AND retired_at IS NULL
) b
  ON a.property_id = b.property_id AND a.field = b.field AND a.doc_id != b.doc_id
WHERE
  (a.field IN ('gla_sqft', 'lot_sqft')
     AND ABS(a.value_numeric - b.value_numeric) / NULLIF(b.value_numeric, 0) > ${G1_TOL_AREA})
  OR (a.field = 'year_built' AND ABS(a.value_numeric - b.value_numeric) > 1)
  OR (a.field IN ('beds', 'baths_full', 'baths_half', 'pool', 'garage_spaces', 'condition_c', 'quality_q')
     AND a.value_numeric != b.value_numeric)
GROUP BY a.fact_id;
-- NOTE: the column list in the UNION above must match facts_staged exactly; generate it in Python.

-- Final status: held if low confidence, out of range, or in conflict.
-- pipeline/g1.py applies ranges from settings, writes facts with status + hold_reasons,
-- and inserts val_ops.review_items (source='g1_hold', route='adjudication' for conflicts,
-- 'steward' for low confidence / out of range).

-- 3.4 Chunks → embeddings
INSERT INTO `${PROJECT}.val_core.chunks` (chunk_id, doc_id, property_id, page, section, text, embedding, created_at)
SELECT chunk_id, doc_id, property_id, page, section, content AS text,
       ml_generate_embedding_result AS embedding, CURRENT_TIMESTAMP()
FROM ML.GENERATE_EMBEDDING(
  MODEL `${PROJECT}.val_raw.embedder`,
  (SELECT chunk_id, doc_id, property_id, page, section, text AS content
   FROM `${PROJECT}.val_core.chunks_pending`),
  STRUCT(TRUE AS flatten_json_output, 'RETRIEVAL_DOCUMENT' AS task_type)
);
