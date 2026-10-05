-- 02 — Remote models (VERIFY option names and current model IDs before running)
-- Connection `${PROJECT}.${BQ_LOCATION}.vertex` and its IAM come from Terraform.

-- Document AI Layout Parser
CREATE OR REPLACE MODEL `${PROJECT}.val_raw.layout_parser`
REMOTE WITH CONNECTION `${PROJECT}.${BQ_LOCATION}.vertex`
OPTIONS (
  remote_service_type = 'CLOUD_AI_DOCUMENT_V1',
  document_processor = '${DOCAI_PROCESSOR_VERSION_PATH}'   -- projects/../locations/us/processors/../processorVersions/..
);

-- Gemini for hard pages (used with AI.GENERATE / ML.GENERATE_TEXT)
CREATE OR REPLACE MODEL `${PROJECT}.val_raw.gemini_extract`
REMOTE WITH CONNECTION `${PROJECT}.${BQ_LOCATION}.vertex`
OPTIONS (endpoint = '${GEMINI_EXTRACT_MODEL}');

-- Embeddings
CREATE OR REPLACE MODEL `${PROJECT}.val_raw.embedder`
REMOTE WITH CONNECTION `${PROJECT}.${BQ_LOCATION}.vertex`
OPTIONS (endpoint = '${EMBEDDING_MODEL}');
