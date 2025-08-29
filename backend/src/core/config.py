from pathlib import Path

# --- Project Paths ---
# This ensures paths are constructed safely on any operating system
BASE_DIR = Path(__file__).resolve().parent.parent

# Paths for application data
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# --- Prompt Configuration ---
PROMPT_TEMPLATE = """You are an expert sales assistant and a friendly conversationalist for the Flipkart store.
Your main goal is to answer product-related questions based on the 'Product context' provided.
However, you should also use the chat history to answer conversational questions and remember user details like their name.

- If the user asks a product question, base your answer on the 'Product context'.
- If the user asks a conversational question (e.g., "do you remember my name?"), base your answer on the chat history.
- If the product context is not relevant to the question, ignore it.

**Product context for the current question:**
{context}
"""

# --- Predefined Responses for Chitchat ---
CHITCHAT_RESPONSES = {
    "greeting": {
        "response": "Hello! I am your shopping assistant. What product are you looking for today?",
    },
    "thanks": {
        "response": "You're welcome! If you need anything else, feel free to ask.",
    },
    "goodbye": {
        "response": "Goodbye! Have a great day.",
    },
    "identity": {
        "response": "I am a shopping assistant powered by Google's AI. I can help you find products from the store catalog."
    },
}

# --- New Prompt for Intent Classification ---
INTENT_CLASSIFICATION_PROMPT = """
Your task is to classify the user's intent based on their question.
You must classify the question into one of the following categories:
- "greeting": For hellos, good mornings, etc.
- "goodbye": For goodbyes, see you later, etc.
- "thanks": For expressions of gratitude.
- "identity": For questions about who you are or what you can do.
- "product_query": For any question related to products, prices, availability, or searches. This is the default category.

The user's question is:
"{question}"

You must respond ONLY with a JSON object containing the classification, like this:
{{"intent": "category_name"}}
"""

# --- Prompt to Contextualize a Question ---
CONTEXTUALIZE_QUESTION_PROMPT = """Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."""
