resource "google_storage_bucket" "landing" {
  name          = "${var.project_id}-landing"
  location      = var.bq_location
  force_destroy = false
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "evidence" {
  name          = "${var.project_id}-evidence"
  location      = var.bq_location
  force_destroy = false
  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "cache" {
  name          = "${var.project_id}-cache"
  location      = var.bq_location
  force_destroy = false
  uniform_bucket_level_access = true
}
