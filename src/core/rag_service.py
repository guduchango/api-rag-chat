import os
import pandas as pd
import logging
import sys
import json
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from langchain_google_vertexai import VertexAIEmbeddings, VertexAI
from langchain_postgres import PGVector
from sqlalchemy import make_url, create_engine, text
from langchain_core.output_parsers import StrOutputParser
from ..core.config import (
    PROMPT_TEMPLATE,
    INTENT_CLASSIFICATION_PROMPT,
)

# Configure logger
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# --- Global Variables ---
vector_store = None
embeddings_model = None
conversation_memory_store = {}
llm = None

# --- Environment Variables ---
PG_HOST = os.environ.get("DB_HOST")
PG_USER = os.environ.get("DB_USER")
PG_PASSWORD = os.environ.get("DB_PASSWORD")
PG_PORT = os.environ.get("DB_PORT", "5432")
PG_DB_NAME = os.environ.get("DB_NAME")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")


def _get_db_engine():
    """
    Creates and returns an SQLAlchemy engine for local development.
    """
    logger.info("📍 Creating engine for local environment...")

    if not all([PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, PG_DB_NAME]):
        raise ValueError("Missing environment variables for local connection.")

    url = make_url(
        f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
    )
    return create_engine(url)


def setup_embeddings():
    """Initializes the Vertex AI embeddings model."""
    logger.info("⚙️ Initializing Vertex AI embeddings...")

    project_id = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_LOCATION", "us-central1")  # default por si falta

    logger.info(f"📍 Embeddings config -> project: {project_id}, location: {location}")

    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is not set.")

    return VertexAIEmbeddings(
        model_name="text-embedding-004",
        project=project_id,
        location=location,
    )


def initialize_vector_store():
    """Initializes the vector store, LLM, and database connection."""
    global vector_store, embeddings_model, llm
    if not embeddings_model:
        embeddings_model = setup_embeddings()

    if not llm:
        logger.info("⚙️ Initializing Vertex AI LLM (Gemini)...")
        # Usamos un modelo rápido y eficiente para la clasificación
        llm = VertexAI(
            model_name="gemini-2.0-flash-lite-001",
            project=GCP_PROJECT_ID,
            location="us-central1",
        )
        logger.info("✅ LLM initialized.")

    collection_name = "rag_products_collection"
    logger.info(
        f"🔄 Connecting to the vector database (Collection: {collection_name})..."
    )
    engine = _get_db_engine()

    vector_store = PGVector(
        embeddings=embeddings_model,
        collection_name=collection_name,
        connection=engine,
    )

    logger.info("✅ Vector database connection established.")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    logger.info("✅ 'vector' (pg_vector) extension ensured.")


def ingest_data_in_background(csv_path: str):
    """Ingests data from a CSV file into the vector store."""
    if not embeddings_model:
        return
    documents = process_csv_to_documents(csv_path)
    if documents:
        collection_name = "rag_products_collection"
        logger.info(f"⏳ Ingesting {len(documents)} documents...")

        PGVector.from_documents(
            embedding=embeddings_model,
            documents=documents,
            collection_name=collection_name,
            connection=_get_db_engine(),
        )
        logger.info("✅ Data ingestion completed.")


def process_csv_to_documents(csv_path):
    # This function processes a CSV and converts it into LangChain Document objects
    logger.info(f"⏳ Processing file: {csv_path}")
    try:
        df = pd.read_csv(csv_path, on_bad_lines="skip")
        df.dropna(subset=["product_name", "description"], inplace=True)
        df.fillna({"brand": "Unknown"}, inplace=True)
    except FileNotFoundError:
        logger.error(f"❌ ERROR: File not found at '{csv_path}'.")
        return []
    documents = []
    for _, row in df.iterrows():
        # Extract the first image URL safely
        image_url = "#"  # Default value
        image_data = row.get("image")
        if pd.notna(image_data):
            try:
                # The column contains a string representation of a list
                image_list = json.loads(image_data)
                if isinstance(image_list, list) and image_list:
                    image_url = image_list[0]
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    f"Could not parse image URL for product {row['product_name']}: {image_data}"
                )

        category_tree = (
            str(row.get("product_category_tree", "General"))
            .strip('[]"')
            .replace(">>", ">")
        )
        page_content = f"Product: {row['product_name']}. Brand: {row['brand']}. Category: {category_tree}. Description: {row['description']}"
        metadata = {
            "name": row["product_name"],
            "brand": row["brand"],
            "price": str(row.get("retail_price", "N/A")),
            "url": row.get("product_url", "#"),
            "image_url": image_url,
        }
        documents.append(Document(page_content=page_content, metadata=metadata))
    logger.info(f"✅ Created {len(documents)} documents from the CSV.")
    return documents


def classify_intent(question: str) -> str:
    """
    Classifies the user's intent using an LLM to decide if it's a chitchat
    or a product-related query.
    """
    if not llm:
        logger.warning("LLM not initialized, defaulting to product_query.")
        return "product_query"

    logger.info(f"🤖 Classifying intent for question: '{question}'")

    prompt = PromptTemplate.from_template(INTENT_CLASSIFICATION_PROMPT)
    # Usamos un parser de string simple y luego parseamos el JSON manualmente para mayor robustez
    chain = prompt | llm | StrOutputParser()

    try:
        llm_output = chain.invoke({"question": question})
        # El LLM a veces devuelve markdown (```json ... ```), lo limpiamos.
        cleaned_output = (
            llm_output.strip().replace("```json", "").replace("```", "").strip()
        )
        response_json = json.loads(cleaned_output)
        intent = response_json.get("intent", "product_query")
        logger.info(f"✅ Intent classified as: '{intent}'")
        return intent
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(
            f"❌ Error parsing intent JSON from LLM output: '{llm_output}'. Error: {e}. Defaulting to 'product_query'."
        )
        return "product_query"
    except Exception as e:
        logger.error(
            f"❌ An unexpected error occurred during intent classification: {e}. Defaulting to 'product_query'."
        )
        return "product_query"


def get_or_create_memory_for_session(session_id: str):
    # This function gets or creates a conversation memory for a given session ID
    if session_id not in conversation_memory_store:
        conversation_memory_store[session_id] = ConversationBufferWindowMemory(
            k=3, memory_key="chat_history", return_messages=True
        )
    return conversation_memory_store[session_id]


def get_rag_answer(session_id: str, question: str, k: int) -> dict:
    """
    Orchestrates the full RAG chain to get a final answer.
    1. Retrieves context from the vector store.
    2. Invokes the LLM with context, chat history, and the question.
    3. Saves the actual question and LLM answer to memory.
    4. Returns a dictionary with the final answer and the generated prompt.
    """
    if not vector_store or not llm:
        logger.error("Vector store or LLM not initialized. Cannot get RAG answer.")
        error_answer = "I'm sorry, but my knowledge base is currently unavailable. Please try again later."
        return {
            "answer": error_answer,
            "prompt": "Error: Vector store or LLM not initialized.",
        }

    logger.info(f"🧠 Generating RAG answer for session '{session_id}'")

    # 1. Get the retriever
    retriever = vector_store.as_retriever(search_kwargs={"k": k})

    # 2. Get the conversation memory
    memory = get_or_create_memory_for_session(session_id)

    # 3. Retrieve relevant documents
    docs = retriever.invoke(question)
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    logger.info(f"📚 Retrieved {len(docs)} documents for context.")

    # 4. Load chat history
    chat_history = memory.load_memory_variables({}).get("chat_history", "")

    # 5. Create the prompt
    prompt_template = PromptTemplate.from_template(PROMPT_TEMPLATE)
    final_prompt = prompt_template.format(
        chat_history=chat_history, context=context, question=question
    )

    # 6. Invoke the LLM to get the answer
    logger.info("🗣️ Invoking LLM to generate the final answer...")
    answer = llm.invoke(final_prompt).strip()
    logger.info(f"💬 LLM generated answer: '{answer}'")

    # 7. Save the actual question and answer to memory
    memory.save_context({"input": question}, {"output": answer})
    logger.info(f"💾 Saved context to memory for session '{session_id}'.")

    # 8. Return the final answer and the prompt for debugging
    return {"answer": answer, "prompt": final_prompt}
