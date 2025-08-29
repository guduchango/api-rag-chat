from pydantic import BaseModel, Field, EmailStr


# --- Request Schema for a Query ---
class QueryRequest(BaseModel):
    """
    Defines the structure for a chat query request.
    Requires a session ID (as an email) and the user's question.
    """

    session_id: EmailStr = Field(
        ...,
        examples=["user@email.com"],
        description="User's email to identify their chat session.",
    )
    question: str = Field(
        ..., min_length=3, max_length=200, examples=["I'm looking for a dog shampoo"]
    )


# --- Response Schema for the Final Prompt ---
class QueryResponse(BaseModel):
    """
    Defines the structure of the response sent back to the user.
    """

    answer: str
    debug_prompt: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Yes, we have the Sicons All Purpose Arnica Dog Shampoo. It's great for all dog breeds and has a pleasant arnica fragrance.",
                "debug_prompt": "You are an expert sales assistant... **Recent conversation history:**\nHuman: Hi, my name is Alex.\nAI: Hello Alex! How can I help you today? ...",
            }
        }


# --- Response Schema for File Upload ---
class UploadResponse(BaseModel):
    """
    Defines the structure of the response for a file upload.
    """

    filename: str
    message: str

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "flipkart_ecommerce_sample.csv",
                "message": "File received. Processing has started in the background.",
            }
        }
