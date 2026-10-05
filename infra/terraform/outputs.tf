output "landing_bucket" {
  value = google_storage_bucket.landing.name
}

output "vertex_connection_id" {
  value = google_bigquery_connection.vertex.name
}

output "vertex_connection_service_account" {
  value = google_bigquery_connection.vertex.cloud_resource[0].service_account_id
}
