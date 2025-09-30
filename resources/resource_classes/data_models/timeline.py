"""Timeline data models"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseModel


@dataclass
class ContentChunk(BaseModel):
    """Represents chunked content for a `Document` object"""

    chunk_identifier: str
    content: str


@dataclass
class TimelineDocument(BaseModel):
    """Represents a single `Document` within the `Timeline` object"""

    id: str
    title: str
    created_at: datetime
    publisher: Optional[str] = None
    summary: Optional[str] = None
    publisher_link: Optional[str] = None
    content_text: List[ContentChunk] = field(default_factory=list)
    informatieobject: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Timeline(BaseModel):
    """Represents the entire `Timeline` object"""

    identifier: str
    name: str
    documents: List[TimelineDocument] = field(default_factory=list)
    beschrijving: Optional[str] = None
    gegenereerd_op: Optional[datetime] = None

    def doc_by_id(self, doc_id: str) -> Optional[TimelineDocument]:
        """Looks up a `TimelineDocument` object by it's identifier"""

        return next((d for d in self.documents if d.id == doc_id), None)
