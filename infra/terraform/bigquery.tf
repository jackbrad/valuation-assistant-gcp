resource "google_bigquery_dataset" "val_raw" {
  dataset_id  = "val_raw"
  location    = var.bq_location
  description = "Landing object tables, raw parser output, and extraction cache"
}

resource "google_bigquery_dataset" "val_core" {
  dataset_id  = "val_core"
  location    = var.bq_location
  description = "Properties, bitemporal facts, golden records, and features"
}

resource "google_bigquery_dataset" "val_ml" {
  dataset_id  = "val_ml"
  location    = var.bq_location
  description = "BQML models, training views, and adjustment grids"
}

resource "google_bigquery_dataset" "val_ops" {
  dataset_id  = "val_ops"
  location    = var.bq_location
  description = "Governance review queue, two-approver decisions, corrections, and breaker state"
}

resource "google_bigquery_connection" "vertex" {
  connection_id = "vertex"
  location      = var.bq_location
  cloud_resource {}
}
