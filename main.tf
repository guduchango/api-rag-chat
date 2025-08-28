# --- Basic Variables ---
variable "docker_image_tag" {
  type        = string
  description = "The Docker image tag to deploy (e.g., the git commit SHA)."
  default     = "v1" # A default value if not specified
}
variable "gcp_project_id" {
  type        = string
  description = "The Google Cloud project ID."
}

variable "gcp_region" {
  type        = string
  description = "The GCP region to deploy resources in."
  default     = "us-central1"
}

# --- Terraform Configuration ---
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# --- Enable Required APIs ---
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",              # For Cloud Run
    "artifactregistry.googleapis.com", # For storing the Docker image
    "sqladmin.googleapis.com"          # For Cloud SQL
  ])

  service            = each.value
  disable_on_destroy = false
}

# --- Secure Database Password ---
resource "random_password" "db_password" {
  length  = 16
  special = true
}

# --- PostgreSQL Database ---
resource "google_sql_database_instance" "postgres" {
  name             = "rag-postgres"
  database_version = "POSTGRES_15"
  region           = var.gcp_region

  settings {
    tier = "db-f1-micro" # The cheapest tier

    # Allow public access (simpler for getting started)
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        value = "0.0.0.0/0" # ⚠️ Access from any IP - for testing only
        name  = "all"
      }
    }
  }

  deletion_protection = false # To allow easy deletion during testing

  depends_on = [google_project_service.required_apis]
}

# --- Specific Database ---
resource "google_sql_database" "app_db" {
  instance = google_sql_database_instance.postgres.name
  name     = "rag_db"
}

# --- Database User ---
resource "google_sql_user" "app_user" {
  instance = google_sql_database_instance.postgres.name
  name     = "rag_user"
  password = random_password.db_password.result
}

# --- Service Account for the Application ---
resource "google_service_account" "api_service_account" {
  account_id   = "api-rag-sa"
  display_name = "Service Account for RAG API"
  description  = "Service account for the RAG API"
}

# --- Minimum Required Permissions ---
resource "google_project_iam_member" "ai_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.api_service_account.email}"
}

# --- Docker Image Repository ---
resource "google_artifact_registry_repository" "docker_repo" {
  repository_id = "rag-app"
  format        = "DOCKER"
  location      = var.gcp_region

  depends_on = [google_project_service.required_apis]
}

# --- Cloud Run Service (Docker container) ---
resource "google_cloud_run_v2_service" "app" {
  name     = "rag-app"
  location = var.gcp_region

  template {
    service_account = google_service_account.api_service_account.email

    containers {
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/rag-app/rag-api:${var.docker_image_tag}"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          memory = "1Gi"
          cpu    = "1"
        }
      }

      # Environment variables for the application container
      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.postgres.public_ip_address
      }

      env {
        name  = "DB_NAME"
        value = "rag_db"
      }

      env {
        name  = "DB_USER"
        value = "rag_user"
      }

      env {
        name  = "DB_PASSWORD"
        value = random_password.db_password.result
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
    }
  }
}

# --- Make the app public (accessible from the internet) ---
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  location = var.gcp_region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Outputs ---
output "app_url" {
  description = "URL of your application."
  value       = google_cloud_run_v2_service.app.uri
}

output "db_connection_info" {
  description = "Information to connect to the database."
  value = {
    host     = google_sql_database_instance.postgres.public_ip_address
    database = "rag_db"
    user     = "rag_user"
    password = random_password.db_password.result
  }
  sensitive = true
}

output "service_account_email" {
  description = "Email of the Service Account to generate credentials."
  value       = google_service_account.api_service_account.email
}

output "docker_repository" {
  description = "Repository where you should upload your Docker image."
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/rag-app"
}
