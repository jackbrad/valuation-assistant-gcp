"""Vector retrieval over cleaned document chunks in BigQuery.

The pipeline (pipeline/run_pipeline.py) writes each cleaned chunk to
val_core.chunks with doc_id, page, section, text and a text-embedding-005
vector. Here we embed the question with the same model and let BigQuery
VECTOR_SEARCH return the closest chunks, filtered to one property.
Heading-only chunks (60 characters or fewer) are skipped.
"""
from typing import Any, Dict, List, Optional

from google.cloud import bigquery

from config.loader import settings

_PROJECT = settings["project"]["project_id"]
_REGION = settings["project"].get("region", "us-central1")
_EMBED_MODEL = settings["models"]["embedding"]

VECTOR_SEARCH_SQL = f"""
SELECT
  base.chunk_id,
  base.doc_id,
  base.page,
  base.section,
  base.text,
  distance
FROM VECTOR_SEARCH(
  (SELECT * FROM `{_PROJECT}.val_core.chunks` WHERE property_id = @property_id AND LENGTH(text) > 60),
  'embedding',
  (SELECT @query_embedding AS embedding),
  top_k => @top_k,
  distance_type => 'COSINE'
)
ORDER BY distance
"""

_embedder = None
_bq: Optional[bigquery.Client] = None


def embed_query(text: str) -> List[float]:
    """Embeds the question with the same model used for the chunks."""
    global _embedder
    if _embedder is None:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel

        vertexai.init(project=_PROJECT, location=_REGION)
        _embedder = TextEmbeddingModel.from_pretrained(_EMBED_MODEL)
    return [float(v) for v in _embedder.get_embeddings([text])[0].values]


def vector_search(property_id: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Returns the top_k chunks for this property, closest first, with citations."""
    global _bq
    if _bq is None:
        _bq = bigquery.Client(project=_PROJECT)

    job = _bq.query(
        VECTOR_SEARCH_SQL,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("property_id", "STRING", property_id),
                bigquery.ArrayQueryParameter("query_embedding", "FLOAT64", embed_query(query)),
                bigquery.ScalarQueryParameter("top_k", "INT64", top_k),
            ]
        ),
    )
    return [
        {
            "doc_id": r["doc_id"],
            "page": int(r["page"]),
            "section": r["section"],
            "text": r["text"],
            "similarity": round(1.0 - float(r["distance"]), 3),
        }
        for r in job.result()
    ]
