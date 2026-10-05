variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
  default     = "takehome-gcp"
}

variable "region" {
  description = "Default Google Cloud compute region"
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery dataset and connection multi-region location"
  type        = string
  default     = "US"
}

variable "docai_location" {
  description = "Document AI processor location"
  type        = string
  default     = "us"
}

variable "name_prefix" {
  description = "Resource name prefix"
  type        = string
  default     = "val"
}
