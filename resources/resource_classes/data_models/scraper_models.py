"""Data models used by the scraper domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .base import BaseModel

DocumentMetadata = Dict[str, Any]


@dataclass(frozen=True)
class SearchQuery(BaseModel):
    """Value object describing a search query against the document repository."""

    term: str
    document_types: List[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "term", self.term.strip())
        object.__setattr__(self, "document_types", list(self.document_types or []))


@dataclass(frozen=True)
class RawDocument(BaseModel):
    """Container for a scraped document with resolved metadata."""

    publisher_link: str
    document_link: str
    metadata: DocumentMetadata

    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dictionary representation."""
        return self.to_dict()


@dataclass
class DocumentSearchResult(BaseModel):
    """Aggregates the outcome of a single repository search call."""

    query: SearchQuery
    documents: List[RawDocument]
    total_pages: int
    page_document_ids: Dict[int, List[str]]

    @property
    def document_count(self) -> int:
        return len(self.documents)

    def documents_as_dicts(self) -> List[Dict[str, Any]]:
        """Convenience helper for consumers expecting dictionaries."""
        return [doc.as_dict() for doc in self.documents]
