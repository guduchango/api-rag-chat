from fastapi import (
    APIRouter,
    UploadFile,
    File,
    BackgroundTasks,
    HTTPException,
    Query,
    Body,
)
import shutil
from ..models.schemas import QueryRequest, QueryResponse, UploadResponse
from ..core.config import UPLOADS_DIR, CHITCHAT_RESPONSES
from ..core import rag_service
import logging
from vertexai.generative_models import GenerativeModel
from vertexai import init

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload-csv", response_model=UploadResponse)
async def upload_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="The uploaded file has no name.")

    file_path = UPLOADS_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(
        rag_service.ingest_data_in_background, csv_path=str(file_path)
    )

    return UploadResponse(
        filename=file.filename,
        message="File received. Data ingestion into the database has started in the background.",
    )


@router.post("/generate-prompt", response_model=QueryResponse)
async def generate_prompt_endpoint(
    request: QueryRequest, k: int = Query(3, ge=1, le=10)
):
    # 1. Clasificar la intención del usuario primero
    intent = rag_service.classify_intent(request.question)

    # 2. Manejar intenciones de chitchat
    if intent in CHITCHAT_RESPONSES:
        response_text = CHITCHAT_RESPONSES[intent]["response"]
        return QueryResponse(final_prompt=response_text)

    # 3. Si la intención es 'product_query', proceder con RAG
    if not rag_service.vector_store:
        raise HTTPException(status_code=503, detail="The vector database is not ready.")

    retriever = rag_service.vector_store.as_retriever(search_kwargs={"k": k})

    final_prompt, memory = rag_service.generate_prompt_with_memory(
        session_id=request.session_id, retriever=retriever, question=request.question
    )

    # Save the context of the conversation
    memory.save_context(
        {"input": request.question},
        {"output": "I have provided relevant information about products."},
    )

    return QueryResponse(final_prompt=final_prompt)


@router.get("/status")
async def get_status():
    # Return the current status of the vector store
    return {
        "status": "ready" if rag_service.vector_store else "initializing",
        "detail": (
            "The vector store is loaded and ready for queries."
            if rag_service.vector_store
            else "The vector store is initializing or no file has been uploaded yet."
        ),
    }


@router.post("/gemini-test")
async def gemini_test(prompt: str = Body(..., embed=True)):
    try:
        project_id = rag_service.GCP_PROJECT_ID
        location = "us-central1"  # o probá con us-central1 si da error

        logger.info(f"🔍 Testing Gemini with project={project_id}, location={location}")

        init(project=project_id, location=location)
        model = GenerativeModel("gemini-2.0-flash-lite-001")
        response = model.generate_content(prompt)

        return {
            "prompt": prompt,
            "response": response.text,
        }

    except Exception as e:
        logger.error(f"❌ Error calling Gemini: {e}")
        raise HTTPException(status_code=500, detail=str(e))
