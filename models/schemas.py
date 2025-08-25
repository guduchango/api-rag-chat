from pydantic import BaseModel, Field, EmailStr
from typing import Optional

# --- Request Schema for a Query ---
class QueryRequest(BaseModel):
    """
    Defines the structure for a chat query request.
    Requires a session ID (as an email) and the user's question.
    """
    session_id: EmailStr = Field(
        ...,
        examples=["user@email.com"],
        description="User's email to identify their chat session."
    )
    question: str = Field(
        ...,
        min_length=3,
        max_length=200,
        examples=["I'm looking for a dog shampoo"]
    )

# --- Response Schema for the Final Prompt ---
class QueryResponse(BaseModel):
    """
    Defines the structure of the response sent back to the user.
    """
    final_prompt: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "final_prompt": "You are an expert sales assistant...\n\n**Product context found:**\nProduct: Sicons All Purpose Arnica Dog Shampoo...\n\n**Customer question:**\nI'm looking for a dog shampoo\n\n**Your answer:"
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
                "message": "File received. Processing has started in the background."
            }
        }