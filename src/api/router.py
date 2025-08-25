from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Query
import shutil
import os
from ..models.schemas import QueryRequest, QueryResponse, UploadResponse
from ..core.config import UPLOADS_DIR
from ..core import rag_service
from sqlalchemy import text, create_engine, make_url
from sqlalchemy.exc import OperationalError
from google.cloud.sql.connector import Connector
import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload-csv", response_model=UploadResponse)
async def upload_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="The uploaded file has no name.")
    
    file_path = UPLOADS_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(rag_service.ingest_data_in_background, csv_path=str(file_path))

    return UploadResponse(
        filename=file.filename,
        message="File received. Data ingestion into the database has started in the background."
    )

@router.post("/generate-prompt", response_model=QueryResponse)
async def generate_prompt_endpoint(request: QueryRequest, k: int = Query(3, ge=1, le=10)):
    # Check for chitchat/small talk before processing the query
    chitchat_response = rag_service.check_for_chitchat(request.question)
    if chitchat_response:
        return QueryResponse(final_prompt=chitchat_response)

    # Ensure the vector store is initialized before proceeding
    if not rag_service.vector_store:
        raise HTTPException(
            status_code=503,
            detail="The vector database is not ready."
        )
    
    retriever = rag_service.vector_store.as_retriever(search_kwargs={"k": k})
    
    final_prompt, memory = rag_service.generate_prompt_with_memory(
        session_id=request.session_id,
        retriever=retriever,
        question=request.question
    )
    
    # Save the context of the conversation
    memory.save_context(
        {"input": request.question}, 
        {"output": "I have provided relevant information about products."}
    )
    
    return QueryResponse(final_prompt=final_prompt)


@router.get("/status")
async def get_status():
    # Return the current status of the vector store
    return {
        "status": "ready" if rag_service.vector_store else "initializing",
        "detail": "The vector store is loaded and ready for queries." if rag_service.vector_store else "The vector store is initializing or no file has been uploaded yet."
    }