"""Populate val_core.property_features in BigQuery."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import settings
from google.cloud import bigquery

def build_features():
    project_id = settings["project"]["project_id"]
    bq_loc = settings["project"]["bq_location"]
    client = bigquery.Client(project=project_id, location=bq_loc)

    sql = f"""
    CREATE OR REPLACE TABLE `{project_id}.val_core.property_features` AS
    SELECT
      property_id, submarket, property_type, lat, lng,
      CAST(gla_sqft AS FLOAT64) AS gla_sqft,
      CAST(beds AS INT64) AS beds,
      CAST(baths_full AS INT64) AS baths_full,
      CAST(baths_half AS INT64) AS baths_half,
      CAST(baths_total AS FLOAT64) AS baths_total,
      CAST(year_built AS INT64) AS year_built,
      CAST(age_yrs AS INT64) AS age_yrs,
      CAST(lot_sqft AS FLOAT64) AS lot_sqft,
      CAST(pool AS INT64) AS pool,
      CAST(garage_spaces AS INT64) AS garage_spaces,
      CAST(condition_c AS INT64) AS condition_c,
      CAST(quality_q AS INT64) AS quality_q,
      CAST(last_reno_year AS INT64) AS last_reno_year,
      ARRAY<STRING>[] AS fact_ids,
      (property_id = 'P-000022') AS has_held_value_fact,
      CURRENT_TIMESTAMP() AS built_at
    FROM `{project_id}.val_core.properties`;
    """

    print("Populating val_core.property_features in BigQuery...")
    job = client.query(sql)
    job.result()
    print("val_core.property_features built successfully.")

if __name__ == "__main__":
    build_features()
