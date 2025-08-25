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
PROMPT_TEMPLATE = """
You are an expert sales assistant for the Flipkart store. Your task is to answer the customer's question in a clear and friendly manner.
Use the conversation history to understand the context, and base your final answer **only and exclusively** on the product information I provide.

**Recent conversation history:**
{chat_history}

**Product context for the current question:**
{context}

**Customer question:**
{question}

**Your answer:**
"""

# --- Predefined Responses for Chitchat ---
CHITCHAT_RESPONSES = {
    "greeting": {
        "keywords": ["hello", "hi", "good day", "good morning", "how are you"],
        "response": "Hello! I am your shopping assistant. What product are you looking for today?"
    },
    "thanks": {
        "keywords": ["thanks", "thank you", "i appreciate it", "very kind"],
        "response": "You're welcome! If you need anything else, feel free to ask."
    },
    "goodbye": {
        "keywords": ["bye", "goodbye", "see you later"],
        "response": "Goodbye! Have a great day."
    }
}