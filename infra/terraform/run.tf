resource "google_cloud_run_v2_service" "valuation_app" {
  name     = "${var.name_prefix}-valuation-app"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/val-repo/valuation-app:latest"
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BQ_LOCATION"
        value = var.bq_location
      }
    }
    scaling {
      min_instance_count = 1
      max_instance_count = 5
    }
  }
}
