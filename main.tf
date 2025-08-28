# main.tf (Versión Minimalista - Solo lo Esencial)

# --- Variables Básicas ---
variable "docker_image_tag" {
  type        = string
  description = "The Docker image tag to deploy (e.g., the git commit SHA)."
  default     = "v1" # Un valor por defecto por si no se especifica
}
variable "gcp_project_id" {
  type        = string
  description = "El ID del proyecto de Google Cloud"
}

variable "gcp_region" {
  type        = string
  description = "La región de GCP para desplegar los recursos"
  default     = "us-central1"
}

# --- Configuración de Terraform ---
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

# --- Habilitación de APIs mínimas necesarias ---
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",           # Para Cloud Run
    "artifactregistry.googleapis.com", # Para guardar la imagen Docker
    "sqladmin.googleapis.com"       # Para Cloud SQL
  ])

  service            = each.value
  disable_on_destroy = false
}

# --- Contraseña segura para la base de datos ---
resource "random_password" "db_password" {
  length  = 16
  special = true
}

# --- Base de datos PostgreSQL ---
resource "google_sql_database_instance" "postgres" {
  name             = "rag-postgres"
  database_version = "POSTGRES_15"
  region           = var.gcp_region

  settings {
    tier = "db-f1-micro"  # La más barata

    # Permitir acceso público (más simple para empezar)
    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        value = "0.0.0.0/0"  # ⚠️ Acceso desde cualquier IP - solo para testing
        name  = "all"
      }
    }
  }

  deletion_protection = false  # Para poder borrar fácilmente en testing

  depends_on = [google_project_service.required_apis]
}

# --- Base de datos específica ---
resource "google_sql_database" "app_db" {
  instance = google_sql_database_instance.postgres.name
  name     = "rag_db"
}

# --- Usuario de la base de datos ---
resource "google_sql_user" "app_user" {
  instance = google_sql_database_instance.postgres.name
  name     = "rag_user"
  password = random_password.db_password.result
}

# --- Service Account para tu aplicación ---
resource "google_service_account" "api_service_account" {
  account_id   = "api-rag-sa"
  display_name = "Service Account for RAG API"
  description  = "Cuenta de servicio para la API RAG"
}

# --- Permisos mínimos necesarios ---
resource "google_project_iam_member" "ai_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.api_service_account.email}"
}

# --- Repositorio para la imagen Docker ---
resource "google_artifact_registry_repository" "docker_repo" {
  repository_id = "rag-app"
  format        = "DOCKER"
  location      = var.gcp_region

  depends_on = [google_project_service.required_apis]
}

# --- Servicio Cloud Run (contenedor Docker) ---
resource "google_cloud_run_v2_service" "app" {
  name     = "rag-app"
  location = var.gcp_region

  template {
    service_account = google_service_account.api_service_account.email

    containers {
      # La imagen que vas a subir
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/rag-app/rag-api:${var.docker_image_tag}"

      ports {
        container_port = 8000
      }

       # --- AÑADE ESTE BLOQUE ---
      resources {
        limits = {
          memory = "1Gi"
          cpu    = "1"
        }
      }

      # Variables de entorno que tu app necesitará
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

# --- Hacer la app pública (accesible desde internet) ---
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  location = var.gcp_region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Información importante que necesitas ---
output "app_url" {
  description = "URL de tu aplicación"
  value       = google_cloud_run_v2_service.app.uri
}

output "db_connection_info" {
  description = "Información para conectar a la base de datos"
  value = {
    host     = google_sql_database_instance.postgres.public_ip_address
    database = "rag_db"
    user     = "rag_user"
    password = random_password.db_password.result
  }
  sensitive = true
}

output "service_account_email" {
  description = "Email de la Service Account para generar credenciales"
  value       = google_service_account.api_service_account.email
}

output "docker_repository" {
  description = "Repositorio donde subir tu imagen Docker"
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project_id}/rag-app"
}
