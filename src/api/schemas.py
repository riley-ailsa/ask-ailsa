"""
API request/response schemas using Pydantic.

These define the contract between API and clients.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal


class GrantSummary(BaseModel):
    """
    Summary representation of a grant (for list/search results).
    """
    id: str
    title: str
    url: str
    source: str
    total_fund: Optional[str] = None
    closes_at: Optional[str] = None
    is_active: bool
    tags: List[str] = Field(default_factory=list)


class GrantDetail(BaseModel):
    """
    Full grant details with metadata.
    """
    id: str
    title: str
    url: str
    source: str
    description: str
    total_fund: Optional[str] = None
    project_size: Optional[str] = None
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None
    is_active: bool
    funding_rules: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    """
    Summary of a document (for grant detail endpoint).
    """
    id: str
    doc_type: str
    scope: str
    source_url: str
    length: int


class GrantWithDocuments(BaseModel):
    """
    Grant with its associated documents.
    """
    grant: GrantDetail
    documents: List[DocumentSummary]


class SearchHit(BaseModel):
    """
    A single search result.
    """
    grant_id: str
    title: str
    source: str = Field(description="Grant source (e.g., innovate_uk, nihr)")
    score: float
    doc_type: str
    scope: str
    source_url: str
    snippet: str = Field(description="Text snippet from document")


class SearchResponse(BaseModel):
    """
    Response from /search endpoint.
    """
    query: str
    total_results: int
    results: List[SearchHit]


class ExplainRequest(BaseModel):
    """
    Request for /search/explain endpoint.

    Note: GPT-5 is used internally. Model selection is not exposed to clients.
    """
    query: str = Field(description="User's search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to consider")


class ReferencedGrant(BaseModel):
    """
    Grant reference in explanation response.
    """
    grant_id: str
    title: str
    url: str
    score: float


class ExplainResponse(BaseModel):
    """
    Response from /search/explain endpoint.
    """
    query: str
    explanation: str
    referenced_grants: List[ReferencedGrant]


class HealthResponse(BaseModel):
    """
    Health check response with hybrid RAG system status.
    """
    status: str
    postgres_grants: int
    pinecone_vectors: int
    timestamp: str
    postgres: Optional[Dict[str, Any]] = None
    pinecone: Optional[Dict[str, Any]] = None
    hybrid_rag: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ChatTurn(BaseModel):
    """
    One turn in the chat history.
    """
    role: Literal["user", "assistant"]
    content: str


class ChatGrant(BaseModel):
    """
    Lightweight grant summary returned with chat answers.
    """
    grant_id: str
    title: str
    url: str
    source: str
    is_active: bool
    total_fund_gbp: Optional[int] = None
    closes_at: Optional[str] = None
    score: float


class ChatRequest(BaseModel):
    """
    Request body for /chat endpoint.
    """
    message: str = Field(description="User's current question or description.")
    history: List[ChatTurn] = Field(
        default_factory=list,
        description="Previous chat turns (user and assistant)."
    )
    # Optional filters – keep simple for now
    active_only: bool = Field(
        default=True,
        description="If true, prefer active grants when possible."
    )
    sources: Optional[List[str]] = Field(
        default=None,
        description="Optional list of sources to include, e.g. ['innovate_uk', 'nihr']."
    )


class ChatResponse(BaseModel):
    """
    Response from /chat endpoint.
    """
    answer: str
    grants: List[ChatGrant] = Field(default_factory=list)
