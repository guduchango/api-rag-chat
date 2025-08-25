import os
import pandas as pd
import logging
import sys
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_postgres import PGVector
from sqlalchemy import make_url, create_engine, text
from ..core.config import PROMPT_TEMPLATE, CHITCHAT_RESPONSES

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
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is not set.")
    return VertexAIEmbeddings(
        model_name="text-embedding-004",
        project=project_id
    )

def initialize_vector_store():
    """Initializes the vector store and database connection."""
    global vector_store, embeddings_model
    if not embeddings_model:
        embeddings_model = setup_embeddings()

    collection_name = "rag_products_collection"
    logger.info(f"🔄 Connecting to the vector database (Collection: {collection_name})...")
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
        df = pd.read_csv(csv_path, on_bad_lines='skip')
        df.dropna(subset=['product_name', 'description'], inplace=True)
        df.fillna({'brand': 'Unknown'}, inplace=True)
    except FileNotFoundError:
        logger.error(f"❌ ERROR: File not found at '{csv_path}'.")
        return []
    documents = []
    for _, row in df.iterrows():
        category_tree = str(row.get('product_category_tree', 'General')).strip('[]"').replace('>>', '>')
        page_content = (f"Product: {row['product_name']}. Brand: {row['brand']}. Category: {category_tree}. Description: {row['description']}")
        metadata = {"name": row['product_name'],"brand": row['brand'],"price": str(row.get('retail_price', 'N/A')),"url": row.get('product_url', '#')}
        documents.append(Document(page_content=page_content, metadata=metadata))
    logger.info(f"✅ Created {len(documents)} documents from the CSV.")
    return documents

def check_for_chitchat(question: str) -> str | None:
    # This function checks if the question is chitchat/small talk
    question_lower = question.lower()
    for intent in CHITCHAT_RESPONSES:
        for keyword in CHITCHAT_RESPONSES[intent]["keywords"]:
            if keyword in question_lower:
                return CHITCHAT_RESPONSES[intent]["response"]
    return None

def get_or_create_memory_for_session(session_id: str):
    # This function gets or creates a conversation memory for a given session ID
    if session_id not in conversation_memory_store:
        conversation_memory_store[session_id] = ConversationBufferWindowMemory(k=3, memory_key="chat_history", return_messages=True)
    return conversation_memory_store[session_id]

def generate_prompt_with_memory(session_id: str, retriever, question: str):
    # This function generates the final prompt using context and conversation history
    memory = get_or_create_memory_for_session(session_id)
    docs = retriever.invoke(question)
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    chat_history = memory.load_memory_variables({})
    prompt_template = PromptTemplate.from_template(PROMPT_TEMPLATE)
    final_prompt = prompt_template.format(chat_history=chat_history.get("chat_history", ""), context=context, question=question)
    return final_prompt, memory