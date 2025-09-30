"""OBM Scraper Service"""

from __future__ import annotations

from typing import List, Sequence

from ..data_models.scraper_models import DocumentSearchResult, SearchQuery
from ..repositories.scraper_repository import DocumentRepository


class DocumentSearchService:
    """Coordinates document searches using the scraper repository layer."""

    def __init__(
        self,
        ttl_dir: str,
        repository: DocumentRepository | None = None,
        max_pages: int = 10,
    ) -> None:
        self.repository = repository or DocumentRepository(ttl_dir)
        self.max_pages = max_pages

    def fetch_documents(
        self,
        search_terms: Sequence[str] | None,
        document_type: Sequence[str] | None = None,
    ) -> List[dict]:
        """Fetch documents matching the supplied search terms and document types."""

        normalized_terms = self._normalize_terms(search_terms)
        if not normalized_terms:
            return []

        document_types = [
            doc_type.strip()
            for doc_type in (document_type or [])
            if doc_type and doc_type.strip()
        ]

        aggregated: List[dict] = []
        for term in normalized_terms:
            result = self._perform_search(term, document_types)
            aggregated.extend(result.documents_as_dicts())

        return aggregated

    def _perform_search(self, term: str, document_types: List[str]) -> DocumentSearchResult:
        query = SearchQuery(term=term, document_types=document_types)
        result = self.repository.search(
            query,
            max_pages=self.max_pages
        )
        self._log_search_result(result)
        return result

    @staticmethod
    def _normalize_terms(search_terms: Sequence[str] | None) -> List[str]:
        if not search_terms:
            return []
        return [term.strip() for term in search_terms if term and term.strip()]

    @staticmethod
    def _log_search_result(result: DocumentSearchResult) -> None:
        """Print the search results for transparency purposes."""

        print(f"In totaal {result.total_pages} pagina's gevonden voor '{result.query.term}'. Document id's per pagina:")
        for page, doc_ids in result.page_document_ids.items():
            print(
                f"[{result.query.term} - pagina {page}] IDs: {len(doc_ids)} -> {doc_ids}"
            )
