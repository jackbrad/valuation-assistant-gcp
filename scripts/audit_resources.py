"""Audit and confirm all provisioned GCP resources from docs/PROVISIONED_RESOURCES.md."""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.cloud import storage, bigquery, documentai_v1 as documentai, pubsub_v1
import google.auth
from config.loader import settings

def audit_gcp():
    project_id = settings["project"]["project_id"]
    bq_loc = settings["project"]["bq_location"]
    docai_loc = settings["project"]["docai_location"]
    
    print(f"==================================================")
    print(f"GCP RESOURCE AUDIT FOR PROJECT: {project_id}")
    print(f"==================================================")

    # 1. Credentials
    credentials, auth_project = google.auth.default()
    print(f"\n[1] Auth & Identity:")
    print(f"  Credentials Type: {type(credentials).__name__}")
    if hasattr(credentials, "service_account_email"):
        print(f"  Service Account:  {credentials.service_account_email}")
    print(f"  Default Project:  {auth_project}")

    # 2. Cloud Storage Buckets
    print(f"\n[2] Cloud Storage Buckets:")
    s_client = storage.Client(project=project_id)
    expected_buckets = [
        f"{project_id}-landing",
        f"{project_id}-evidence",
        f"{project_id}-cache"
    ]
    for b_name in expected_buckets:
        try:
            b = s_client.get_bucket(b_name)
            print(f"  [OK] Bucket: gs://{b.name} (Location: {b.location}, Storage Class: {b.storage_class})")
            if "landing" in b_name:
                blobs = list(s_client.list_blobs(b_name))
                print(f"       Total objects in landing: {len(blobs)}")
                for blob in blobs[:10]:
                    print(f"         - {blob.name} ({blob.size} bytes)")
        except Exception as e:
            print(f"  [FAIL] Bucket: {b_name} -> {e}")

    # 3. BigQuery Datasets & Tables & Models
    print(f"\n[3] BigQuery Architecture (Location: {bq_loc}):")
    bq_client = bigquery.Client(project=project_id, location=bq_loc)
    datasets = ["val_raw", "val_core", "val_ml", "val_ops"]
    for ds_name in datasets:
        ds_id = f"{project_id}.{ds_name}"
        try:
            ds = bq_client.get_dataset(ds_id)
            print(f"  [OK] Dataset: {ds_id} (Location: {ds.location})")
            tables = list(bq_client.list_tables(ds_id))
            print(f"       Tables/Views/Models ({len(tables)}):")
            for t in tables:
                try:
                    table_obj = bq_client.get_table(t.reference)
                    print(f"         - {t.table_id} ({table_obj.table_type}, {table_obj.num_rows} rows)")
                except Exception:
                    print(f"         - {t.table_id} ({t.table_type})")
            # List models
            models = list(bq_client.list_models(ds_id))
            if models:
                print(f"       BQML Models ({len(models)}):")
                for m in models:
                    print(f"         * Model: {m.model_id} (Type: {m.model_type})")
        except Exception as e:
            print(f"  [FAIL] Dataset: {ds_id} -> {e}")

    # 4. BigQuery Connection
    print(f"\n[4] BigQuery Connection:")
    try:
        from google.cloud import bigquery_connection_v1
        conn_client = bigquery_connection_v1.ConnectionServiceClient()
        parent = f"projects/{project_id}/locations/{bq_loc}"
        connections = list(conn_client.list_connections(parent=parent))
        print(f"  Connections in {parent}: {len(connections)}")
        for conn in connections:
            print(f"  [OK] Connection: {conn.name}")
            if conn.cloud_resource:
                print(f"       SA: {conn.cloud_resource.service_account_id}")
    except Exception as e:
        print(f"  [NOTICE] Connection check: {e}")

    # 5. Pub/Sub Topics
    print(f"\n[5] Pub/Sub Topics:")
    ps_publisher = pubsub_v1.PublisherClient()
    for topic_name in ["flags", "corrections"]:
        topic_path = ps_publisher.topic_path(project_id, topic_name)
        try:
            t = ps_publisher.get_topic(request={"topic": topic_path})
            print(f"  [OK] Topic: {t.name}")
        except Exception as e:
            print(f"  [FAIL] Topic: {topic_path} -> {e}")

    # 6. Document AI Processors
    print(f"\n[6] Document AI Processors:")
    try:
        client_options = {"api_endpoint": f"{docai_loc}-documentai.googleapis.com"}
        docai_client = documentai.DocumentProcessorServiceClient(client_options=client_options)
        parent = f"projects/{project_id}/locations/{docai_loc}"
        processors = list(docai_client.list_processors(parent=parent))
        print(f"  Processors in {parent}: {len(processors)}")
        for proc in processors:
            print(f"  [OK] Processor: {proc.display_name} (ID: {proc.name}, State: {proc.state.name}, Type: {proc.type_})")
    except Exception as e:
        print(f"  [FAIL] DocAI check: {e}")

    print(f"\n==================================================")
    print(f"AUDIT COMPLETE")
    print(f"==================================================")

if __name__ == "__main__":
    audit_gcp()
