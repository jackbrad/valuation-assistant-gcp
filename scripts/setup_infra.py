"""Provision GCS buckets, BigQuery datasets, and Pub/Sub topics via Google Cloud Python SDK."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import settings


def setup_infrastructure(dry_run: bool = False):
    proj_cfg = settings["project"]
    project_id = proj_cfg["project_id"]
    bq_loc = proj_cfg["bq_location"]
    region = proj_cfg["region"]

    landing_bucket = f"{project_id}-landing"
    evidence_bucket = f"{project_id}-evidence"
    cache_bucket = f"{project_id}-cache"

    datasets = ["val_raw", "val_core", "val_ml", "val_ops"]
    topics = ["flags", "corrections"]

    print(f"Target Project: {project_id}")
    print(f"Buckets: {[landing_bucket, evidence_bucket, cache_bucket]}")
    print(f"BigQuery Datasets ({bq_loc}): {datasets}")
    print(f"Pub/Sub Topics: {topics}")

    if dry_run:
        print("[Dry Run] Skipping cloud resource creation.")
        return 0

    try:
        from google.cloud import storage, bigquery, pubsub_v1
        from google.api_core.exceptions import Conflict

        # 1. Cloud Storage
        print("\nCreating GCS buckets...")
        s_client = storage.Client(project=project_id)
        for b_name in [landing_bucket, evidence_bucket, cache_bucket]:
            try:
                bucket = s_client.create_bucket(b_name, location=bq_loc)
                print(f"  + Bucket created: {b_name}")
            except Conflict:
                print(f"  = Bucket already exists: {b_name}")
            except Exception as e:
                print(f"  ! Error creating bucket {b_name}: {e}")

        # 2. BigQuery Datasets
        print("\nCreating BigQuery datasets...")
        bq_client = bigquery.Client(project=project_id, location=bq_loc)
        for ds_name in datasets:
            ds_id = f"{project_id}.{ds_name}"
            ds = bigquery.Dataset(ds_id)
            ds.location = bq_loc
            try:
                bq_client.create_dataset(ds, exists_ok=True)
                print(f"  + Dataset ready: {ds_id}")
            except Exception as e:
                print(f"  ! Error creating dataset {ds_id}: {e}")

        # 3. Pub/Sub Topics
        print("\nCreating Pub/Sub topics...")
        ps_publisher = pubsub_v1.PublisherClient()
        for t_name in topics:
            topic_path = ps_publisher.topic_path(project_id, t_name)
            try:
                ps_publisher.create_topic(request={"name": topic_path})
                print(f"  + Topic created: {topic_path}")
            except Conflict:
                print(f"  = Topic already exists: {topic_path}")
            except Exception as e:
                print(f"  ! Error creating topic {t_name}: {e}")

        print("\nInfrastructure provisioning finished.")
        return 0
    except Exception as e:
        print(f"\nInfrastructure setup error: {e}")
        return 1


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sys.exit(setup_infrastructure(dry_run=dry_run))
