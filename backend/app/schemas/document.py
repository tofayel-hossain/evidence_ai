from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ExtractedPage(BaseModel):
    page_number: int = Field(..., description="1-indexed document page number")
    text: str = Field(..., description="Extracted raw text of the page")
    char_count: int = Field(..., description="Total characters in this page")
    is_empty: bool = Field(False, description="Whether the page contains no extractable text")

class ExtractionResult(BaseModel):
    success: bool
    filename: str
    page_count: int
    pages: List[ExtractedPage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_scanned: bool = Field(False, description="True if no extractable text found across all pages")
    error_message: Optional[str] = None

class DocumentBase(BaseModel):
    filename: str
    file_size_bytes: int
    page_count: int = 0
    title: Optional[str] = None
    author: Optional[str] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: str
    user_id: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class DocumentChunkDTO(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    page_number: int
    content: str
    token_count: int
    start_char: int
    end_char: int

    model_config = {"from_attributes": True}
