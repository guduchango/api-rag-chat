import os
import pandas as pd
import logging
import sys
import json
from langchain_core.documents import Document
from langchain_core.prompts import (
    PromptTemplate,
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain.memory import ConversationBufferWindowMemory
from langchain_google_vertexai import VertexAIEmbeddings, VertexAI
from langchain_postgres import PGVector
from sqlalchemy import make_url, create_engine, text
from sqlalchemy.orm import sessionmaker, joinedload
from langchain_core.output_parsers import StrOutputParser
from langchain.chains import (
    create_history_aware_retriever,
)
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain

from ..core.config import (
    PROMPT_TEMPLATE,
    INTENT_CLASSIFICATION_PROMPT,
    CONTEXTUALIZE_QUESTION_PROMPT,
)
from ..models.db_models import Product, ProductVariant, Base

# Configure logger
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

# --- Global Variables ---
vector_store = None
embeddings_model = None
conversation_memory_store = {}
llm = None
db_engine = None
SessionLocal = None


# --- Environment Variables ---
PG_HOST = os.environ.get("DB_HOST")
PG_USER = os.environ.get("DB_USER")
PG_PASSWORD = os.environ.get("DB_PASSWORD")
PG_PORT = os.environ.get("DB_PORT", "5432")
PG_DB_NAME = os.environ.get("DB_NAME")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")


def _get_db_engine():
    """
    Creates and returns an SQLAlchemy engine.
    Caches the engine for reuse.
    """
    global db_engine
    if db_engine is None:
        logger.info("📍 Creating SQLAlchemy engine...")
        if not all([PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, PG_DB_NAME]):
            raise ValueError("Missing environment variables for database connection.")
        url = make_url(
            f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
        )
        db_engine = create_engine(url)
    return db_engine


def setup_embeddings():
    """Initializes the Vertex AI embeddings model."""
    logger.info("⚙️ Initializing Vertex AI embeddings...")
    project_id = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    logger.info(f"📍 Embeddings config -> project: {project_id}, location: {location}")
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is not set.")
    return VertexAIEmbeddings(
        model_name="text-embedding-004", project=project_id, location=location
    )


def initialize_vector_store():
    """
    Initializes the vector store, LLM, and database connection,
    and creates relational tables.
    """
    global vector_store, embeddings_model, llm, SessionLocal
    if not embeddings_model:
        embeddings_model = setup_embeddings()

    if not llm:
        logger.info("⚙️ Initializing Vertex AI LLM (Gemini)...")
        llm = VertexAI(
            model_name="gemini-2.0-flash-lite-001",
            project=GCP_PROJECT_ID,
            location="us-central1",
        )
        logger.info("✅ LLM initialized.")

    engine = _get_db_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    logger.info("🔄 Ensuring relational tables exist...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Relational tables created.")

    collection_name = "rag_products_collection"
    logger.info(
        f"🔄 Connecting to the vector database (Collection: {collection_name})..."
    )
    vector_store = PGVector(
        embeddings=embeddings_model,
        collection_name=collection_name,
        connection=engine,
        use_jsonb=True,
    )
    logger.info("✅ Vector database connection established.")

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    logger.info("✅ 'vector' (pg_vector) extension ensured.")


def create_documents_from_db(products: list[Product]) -> list[Document]:
    """
    Creates LangChain Document objects from a list of Product records.
    """
    documents = []
    for product in products:
        price = "N/A"
        if product.variants:
            # Here we could add logic to show a price range if there are multiple variants
            price = str(product.variants[0].retail_price or "N/A")

        # IMPORTANT: Add the price to the page_content so the LLM can see it.
        page_content = f"Product: {product.name}. Brand: {product.brand}. Category: {product.category_tree}. Price: ${price}. Description: {product.description}"

        metadata = {
            "product_id": product.id,
            "name": product.name,
            "brand": product.brand,
            "price": price,
            "url": product.product_url,
            "image_url": product.image_urls[0] if product.image_urls else "#",
        }
        documents.append(Document(page_content=page_content, metadata=metadata))
    logger.info(f"✅ Created {len(documents)} documents from the database.")
    return documents


def ingest_data_in_background(csv_path: str):
    """
    Orchestrates the data ingestion pipeline from a structured CSV.
    """
    if not embeddings_model or not SessionLocal:
        logger.error("Service not initialized. Cannot ingest data.")
        return

    logger.info(f"⏳ Starting ingestion process for clean file: {csv_path}")
    try:
        df = pd.read_csv(csv_path).astype(str)
    except FileNotFoundError:
        logger.error(f"❌ ERROR: File not found at '{csv_path}'.")
        return

    session = SessionLocal()
    try:
        grouped = df.groupby("product_id")
        new_products = []

        for product_id, group in grouped:
            existing_product = (
                session.query(Product).filter_by(uniq_id=product_id).first()
            )
            if existing_product:
                logger.info(f"Skipping existing product: {product_id}")
                continue

            first_row = group.iloc[0]
            product = Product(
                uniq_id=product_id,
                name=first_row["product_name"],
                category_tree=first_row["category"],
                description=first_row["description"],
                brand=first_row["brand"],
                product_url=first_row["product_url"],
                image_urls=group["image_url"].tolist(),
            )
            session.add(product)
            session.flush()

            for _, row in group.iterrows():
                variant = ProductVariant(
                    product_id=product.id,
                    retail_price=float(row.get("retail_price", 0.0)),
                    discounted_price=float(row.get("discounted_price", 0.0)),
                    stock=100,
                )
                session.add(variant)
            new_products.append(product)

        session.commit()
        logger.info(f"✅ Committed {len(new_products)} new products to the database.")

        if new_products:
            product_ids = [p.id for p in new_products]
            session.close()

            session = SessionLocal()
            hydrated_products = (
                session.query(Product)
                .options(joinedload(Product.variants))
                .filter(Product.id.in_(product_ids))
                .all()
            )

            documents = create_documents_from_db(hydrated_products)
            if documents:
                collection_name = "rag_products_collection"
                logger.info(
                    f"⏳ Ingesting {len(documents)} documents into vector store..."
                )
                PGVector.from_documents(
                    embedding=embeddings_model,
                    documents=documents,
                    collection_name=collection_name,
                    connection=_get_db_engine(),
                    pre_delete_collection=True,
                )
                logger.info("✅ Vector store ingestion completed.")

    except Exception as e:
        logger.error(f"❌ An error occurred during data ingestion: {e}")
        import traceback

        logger.error(traceback.format_exc())
        session.rollback()
    finally:
        session.close()


def classify_intent(question: str) -> str:
    """
    Classifies the user's intent.
    """
    if not llm:
        logger.warning("LLM not initialized, defaulting to product_query.")
        return "product_query"

    logger.info(f"🤖 Classifying intent for question: '{question}'")
    prompt = PromptTemplate.from_template(INTENT_CLASSIFICATION_PROMPT)
    chain = prompt | llm | StrOutputParser()

    try:
        llm_output = chain.invoke({"question": question})
        cleaned_output = (
            llm_output.strip().replace("```json", "").replace("```", "").strip()
        )
        response_json = json.loads(cleaned_output)
        intent = response_json.get("intent", "product_query")
        logger.info(f"✅ Intent classified as: '{intent}'")
        return intent
    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(
            f"❌ Error parsing intent JSON from LLM output: '{llm_output}'. Error: {e}."
        )
        return "product_query"
    except Exception as e:
        logger.error(f"❌ Unexpected error during intent classification: {e}.")
        return "product_query"


def get_or_create_memory_for_session(session_id: str):
    if session_id not in conversation_memory_store:
        conversation_memory_store[session_id] = ConversationBufferWindowMemory(
            k=10, memory_key="chat_history", return_messages=True
        )
    return conversation_memory_store[session_id]


def get_rag_answer(session_id: str, question: str, k: int) -> dict:
    """
    Orchestrates the full RAG chain with history-aware retrieval.
    """
    if not vector_store or not llm:
        logger.error("Vector store or LLM not initialized.")
        return {
            "answer": "I'm sorry, but my knowledge base is currently unavailable.",
            "prompt": "Error: Not initialized.",
        }

    logger.info(f"🧠 Generating RAG answer for session '{session_id}'")
    retriever = vector_store.as_retriever(search_kwargs={"k": k})
    memory = get_or_create_memory_for_session(session_id)

    # 1. Create a history-aware retriever
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CONTEXTUALIZE_QUESTION_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )

    # 2. Create the main chain to answer the question
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PROMPT_TEMPLATE),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    # 3. Create the final retrieval chain
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    # 4. Invoke the chain with the current question and history
    chat_history = memory.load_memory_variables({}).get("chat_history", [])
    response = rag_chain.invoke({"input": question, "chat_history": chat_history})

    # 5. Save the new context to memory
    memory.save_context({"input": question}, {"output": response["answer"]})
    logger.info(f"💾 Saved context to memory for session '{session_id}'.")

    # 6. Format the debug prompt with history and context
    history_from_response = response.get("chat_history", [])
    formatted_history = "\n".join(
        [f"{msg.__class__.__name__}: {msg.content}" for msg in history_from_response]
    )
    retrieved_docs = "\n---\n".join([doc.page_content for doc in response["context"]])

    debug_prompt = (
        f"--- Chat History Sent to Prompt ---\n{formatted_history}\n\n"
        f"--- Retrieved Context ---\n{retrieved_docs}"
    )

    return {"answer": response["answer"], "prompt": debug_prompt}
