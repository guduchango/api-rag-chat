# main.py - Con debugging mejorado para Cloud Run

from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import os
import sys
import logging
from dotenv import load_dotenv

from .api import router as api_router
from .core import rag_service

# Configurar logging para Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Carga el .env solo si existe
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida de la aplicación.
    """
    logger.info("=== INICIANDO APLICACIÓN ===")

    # Debug: Mostrar todas las variables de entorno
    logger.info("📋 Variables de entorno:")
    for key, value in os.environ.items():
        if any(x in key.upper() for x in ["DB_", "GCP_", "GOOGLE_"]):
            # Ocultar passwords
            display_value = "***HIDDEN***" if "PASSWORD" in key.upper() else value
            logger.info(f"  {key}={display_value}")

    try:
        # Verificar proyecto
        project_id = os.environ.get("GCP_PROJECT_ID")
        if not project_id:
            logger.warning("⚠️  GCP_PROJECT_ID no configurado, usando default")
            os.environ["GCP_PROJECT_ID"] = "rag-project-469718"

        logger.info(f"🌍 Proyecto GCP: {os.environ.get('GCP_PROJECT_ID')}")
        logger.info(f"🌍 Región GCP: {os.environ.get('GCP_REGION', 'us-central1')}")

        # Verificar credenciales
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            logger.info(f"🔑 Credenciales encontradas en: {creds_path}")
            if os.path.exists(creds_path):
                logger.info("✅ Archivo de credenciales existe")
            else:
                logger.error("❌ Archivo de credenciales NO existe")
        else:
            logger.info("🔑 Usando Service Account de Cloud Run")

        # Inicializar vector store
        logger.info("🔄 Inicializando vector store...")
        rag_service.initialize_vector_store()
        logger.info("✅ Vector store inicializado correctamente")

    except Exception as e:
        logger.error(f"❌ ERROR durante inicialización: {str(e)}")
        logger.error(f"📍 Tipo de error: {type(e).__name__}")
        import traceback

        logger.error(f"📍 Traceback completo:\n{traceback.format_exc()}")
        # No fallar completamente
        logger.warning("⚠️  Continuando sin vector store...")

    logger.info("🚀 Aplicación lista para recibir peticiones")

    yield

    logger.info("=== APAGANDO APLICACIÓN ===")


# Crear app
app = FastAPI(
    title="API de Asistente RAG (Cloud-Native)",
    description="Una API para generar prompts RAG usando Vertex AI y Cloud SQL.",
    version="2.0.0",
    lifespan=lifespan,
)

# Incluir rutas
app.include_router(api_router.router, prefix="/api")


@app.get("/", tags=["Root"])
async def read_root():
    return {
        "message": "Bienvenido a la API del Asistente RAG v2. Ve a /docs para la documentación."
    }


@app.get("/debug", tags=["Debug"])
async def debug_info():
    """Endpoint para debugging - mostrar info del entorno"""
    return {
        "status": "running",
        "environment": "cloud" if not os.environ.get("DB_HOST") else "local",
        "project_id": os.environ.get("GCP_PROJECT_ID"),
        "region": os.environ.get("GCP_REGION"),
        "has_credentials": bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")),
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "files_in_app": os.listdir("/app") if os.path.exists("/app") else [],
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    try:
        # Intentar una operación simple para verificar que todo funciona
        return {
            "status": "healthy",
            "timestamp": "ok",
            "environment": "cloud" if not os.environ.get("DB_HOST") else "local",
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"🚀 Iniciando servidor en puerto {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
