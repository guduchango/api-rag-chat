#!/bin/bash
set -e

# --- Configuración ---
PROJECT_ID="rag-project-469718"
REGION="us-central1"
REPO="rag-app"
IMAGE="rag-api" # ¡Nombre corregido!
TAG="v1"

# --- Autenticación ---
echo "🔑 Autenticando Docker..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# --- Construir imagen ---
echo "📦 Construyendo imagen Docker..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:${TAG} .

# --- Subir imagen ---
echo "🚀 Subiendo imagen a Artifact Registry..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:${TAG}

echo "✅ Imagen subida con éxito."
# LA LÍNEA DE gcloud run deploy SE ELIMINA