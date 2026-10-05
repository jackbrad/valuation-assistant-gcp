"""Run BigQuery SQL scripts with placeholder substitution."""
import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import settings

def substitute_placeholders(sql_text: str) -> str:
    proj_cfg = settings.get("project", {})
    project = proj_cfg.get("project_id", "takehome-gcp")
    bq_loc = proj_cfg.get("bq_location", "US")
    landing_bucket = f"{project}-landing"
    models_cfg = settings.get("models", {})
    gemini_model = models_cfg.get("gemini_extract", "gemini-1.5-flash")
    embed_model = models_cfg.get("embedding", "text-embedding-004")
    docai_proc = "projects/281362663093/locations/us/processors/c745df858c6e37e0"

    sql = sql_text.replace("${PROJECT}", project)
    sql = sql.replace("${BQ_LOCATION}", bq_loc)
    sql = sql.replace("${LANDING_BUCKET}", landing_bucket)
    sql = sql.replace("${DOCAI_PROCESSOR_VERSION_PATH}", docai_proc)
    sql = sql.replace("${GEMINI_EXTRACT_MODEL}", gemini_model)
    sql = sql.replace("${EMBEDDING_MODEL}", embed_model)
    return sql

def execute_sql(sql_content: str, dry_run: bool = False):
    sql_to_run = substitute_placeholders(sql_content)
    
    if dry_run:
        print("=== DRY RUN SQL ===")
        print(sql_to_run[:1000] + ("\n..." if len(sql_to_run) > 1000 else ""))
        return 0

    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings["project"]["project_id"], location=settings["project"]["bq_location"])
        print(f"Executing query on BigQuery ({settings['project']['project_id']})...")
        job = client.query(sql_to_run)
        job.result()
        print("Query executed successfully.")
        return 0
    except Exception as e:
        print(f"BigQuery execution failed: {e}")
        print("(Note: If credentials are not yet set up, use --dry-run)")
        return 1

def main():
    parser = argparse.ArgumentParser(description="Run SQL against BigQuery with settings substitution.")
    parser.add_argument("--file", "-f", required=True, help="Path to SQL file")
    parser.add_argument("--dry-run", action="store_true", help="Print substituted SQL without executing")
    args = parser.parse_args()

    sql_path = Path(args.file)
    if not sql_path.exists():
        print(f"File not found: {sql_path}")
        return 1

    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()

    return execute_sql(content, dry_run=args.dry_run)

if __name__ == "__main__":
    sys.exit(main())
