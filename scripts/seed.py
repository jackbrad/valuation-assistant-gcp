"""Seed synthetic data and documents to GCS and BigQuery."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import settings


def seed_data(dry_run: bool = False):
    proj_cfg = settings["project"]
    project_id = proj_cfg["project_id"]
    bq_loc = proj_cfg["bq_location"]
    landing_bucket = f"{project_id}-landing"
    out_dir = Path("data_gen/out")

    print(f"Seeding synthetic data to Project: {project_id}")
    print(f"Data directory: {out_dir}")

    csv_files = {
        "val_raw.manifest": out_dir / "manifest.jsonl",
        "val_core.properties": out_dir / "public_records.csv",
        "val_core.sales": out_dir / "sales.csv",
        "val_core.market_index": out_dir / "market_index.csv",
        "val_ops.comp_feedback": out_dir / "comp_feedback.csv",
    }

    if dry_run:
        print("\n[Dry Run] Validating generated files:")
        for table, path in csv_files.items():
            print(f"  * {table} <- {path} (exists: {path.exists()})")
        pdfs_dir = out_dir / "pdfs"
        print(f"  * GCS upload: {pdfs_dir} -> gs://{landing_bucket}/ (exists: {pdfs_dir.exists()})")
        return 0

    try:
        from google.cloud import storage, bigquery

        # 1. Upload PDFs to GCS
        print(f"\nUploading demo PDFs to gs://{landing_bucket}/...")
        s_client = storage.Client(project=project_id)
        bucket = s_client.bucket(landing_bucket)
        pdfs_dir = out_dir / "pdfs"

        for pdf_path in pdfs_dir.rglob("*.pdf"):
            rel_path = pdf_path.relative_to(pdfs_dir)
            blob = bucket.blob(str(rel_path))
            blob.upload_from_filename(str(pdf_path))
            print(f"  + Uploaded gs://{landing_bucket}/{rel_path}")

        # 2. Load CSVs to BigQuery
        print("\nLoading tables into BigQuery...")
        bq_client = bigquery.Client(project=project_id, location=bq_loc)
        
        # Load properties
        if (out_dir / "public_records.csv").exists():
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                autodetect=True,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            )
            with open(out_dir / "public_records.csv", "rb") as f:
                table_id = f"{project_id}.val_core.properties"
                job = bq_client.load_table_from_file(f, table_id, job_config=job_config)
                job.result()
                print(f"  + Loaded {table_id}")

        # Load sales
        if (out_dir / "sales.csv").exists():
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                autodetect=True,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            )
            with open(out_dir / "sales.csv", "rb") as f:
                table_id = f"{project_id}.val_core.sales"
                job = bq_client.load_table_from_file(f, table_id, job_config=job_config)
                job.result()
                print(f"  + Loaded {table_id}")

        # Load market index
        if (out_dir / "market_index.csv").exists():
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                autodetect=True,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            )
            with open(out_dir / "market_index.csv", "rb") as f:
                table_id = f"{project_id}.val_core.market_index"
                job = bq_client.load_table_from_file(f, table_id, job_config=job_config)
                job.result()
                print(f"  + Loaded {table_id}")

        # Load comp feedback
        if (out_dir / "comp_feedback.csv").exists():
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                autodetect=True,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            )
            with open(out_dir / "comp_feedback.csv", "rb") as f:
                table_id = f"{project_id}.val_ops.comp_feedback"
                job = bq_client.load_table_from_file(f, table_id, job_config=job_config)
                job.result()
                print(f"  + Loaded {table_id}")

        print("\nData seeding completed successfully.")
        return 0
    except Exception as e:
        print(f"\nData seeding failed: {e}")
        print("(Use --dry-run if credentials are not yet set up)")
        return 1


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(seed_data(dry_run=dry_run))
