# IAM permissions for BigQuery Connection Service Account
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_bigquery_connection.vertex.cloud_resource[0].service_account_id}"
}

resource "google_project_iam_member" "docai_viewer" {
  project = var.project_id
  role    = "roles/documentai.viewer"
  member  = "serviceAccount:${google_bigquery_connection.vertex.cloud_resource[0].service_account_id}"
}

resource "google_project_iam_member" "storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_bigquery_connection.vertex.cloud_resource[0].service_account_id}"
}
