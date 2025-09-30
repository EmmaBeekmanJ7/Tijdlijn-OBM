from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any, List, Sequence

from dotenv import load_dotenv
from opensearchpy import OpenSearch
from tqdm import tqdm

from resource_classes import DocumentsNotFound, TimelineNotFound
from ..data_models.timeline import Timeline as TimelineModel, TimelineDocument, ContentChunk
from ..repositories.timeline_repository import TimelineRepository
from ..services.cl_mistral_completions import CL_Mistral_Completions
from ..services.processor import DocumentProcessor
from ..services.scraper import DocumentSearchService

load_dotenv()

AVAILABLE_DOCUMENT_TYPES = [
    "Alle parlementaire documenten",
    "Handelingen",
    "Motie",
    "Kamervragen",
    "Kamerstukken",
    "Agenda's",
]

DEFAULT_TIMELINE_INDEX = "es_minfin_tijdlijnen"


class Timeline:
    """
    Service class for generating, processing, and storing timelines.

    Responsibilities:
    - Fetch raw documents based on search terms and document type.
    - Process documents into structured content.
    - Upsert timelines into OpenSearch, including metadata and summaries.
    """

    def __init__(
        self,
        opensearch_client: OpenSearch | None = None,
        repository: TimelineRepository | None = None,
        index: str | None = None,
    ) -> None:
        """Configure dependencies for the timeline service."""

        base_dir = os.getcwd()
        ttl_dir = os.path.join(base_dir, "resources", "MetaDocuments")

        self.scraper = DocumentSearchService(ttl_dir=ttl_dir)
        self.processor = DocumentProcessor()
        self.opensearch = opensearch_client or self._create_opensearch_client()
        repo_index = index or os.getenv(
            "OPENSEARCH_TIMELINE_INDEX", DEFAULT_TIMELINE_INDEX
        )
        self.repo = repository or TimelineRepository(self.opensearch, index=repo_index)
        self.client = CL_Mistral_Completions(
            model="mistral-small-latest", temperature=0.3
        )

    def generate(self) -> dict:
        """
        Generate a timeline for the given search terms and document types.

        Steps:
        1. Fetch raw documents using DocumentSearchService.
        2. Process documents into structured form using DocumentProcessor.
        3. Create a timeline name (first search term) and identifier.
        4. Upsert the timeline including all documents into OpenSearch.
        """
        user_input = self._get_search_input()

        results = self.scraper.fetch_documents(
            search_terms=user_input.get("search_terms"),
            document_type=user_input.get("document_type"),
        )

        documents_to_add = self.processor.process(results)
        if not documents_to_add:
            raise DocumentsNotFound("Geen documenten gevonden of verwerkt.")

        timeline_name = (
            user_input.get("search_terms")[0] if user_input.get("search_terms") else "Onbekend"  # type: ignore
        )
        timeline_id = hashlib.md5(timeline_name.encode("utf-8")).hexdigest()

        timeline = self._build_timeline(timeline_name, timeline_id, documents_to_add)
        self.repo.upsert(timeline)

        return {
            "name": timeline.name,
            "id": timeline.identifier,
            "documents_count": len(timeline.documents),
        }

    def summarize(
        self, tijdlijn_id: str | None = None, doc_id: str | None = None
    ) -> None:
        """Update summaries for one document or the entire timeline."""
        selected_timeline_id = tijdlijn_id or self._get_summary_input()
        if not selected_timeline_id:
            return

        timeline = self.repo.get(selected_timeline_id)
        if timeline is None:
            raise TimelineNotFound(f"Timeline {selected_timeline_id} niet gevonden.")

        timeline = self._normalize_timeline(timeline)
        target_doc_id = doc_id or self._get_single_doc_input(timeline)

        if target_doc_id:
            updated_timeline = self._update_single_doc_summary(timeline, target_doc_id)
        else:
            updated_timeline = self._update_all_summaries(timeline)

        self.repo.update(updated_timeline)

    def _create_opensearch_client(self) -> OpenSearch:
        """Instantiate an OpenSearch client based on environment configuration."""
        url = os.getenv("OPENSEARCH_URL")
        username = os.getenv("OPENSEARCH_USERNAME")
        password = os.getenv("OPENSEARCH_PASSWORD")

        if not url or not username or not password:
            raise ValueError("OpenSearch-configuratie ontbreekt in de omgeving.")

        return OpenSearch(
            url,
            http_auth=(username, password),
            request_timeout=900,
            verify_certs=False,
        )

    def _build_timeline(
        self, timeline_name: str, timeline_id: str, documents: List[dict]
    ) -> TimelineModel:
        """Convert processed documents into a `Timeline` data model."""

        timeline_documents = self._build_timeline_documents(documents)
        timeline = TimelineModel(
            identifier=timeline_id,
            name=timeline_name,
            documents=timeline_documents,
        )
        return self._normalize_timeline(timeline)

    def _build_timeline_documents(
        self, documents: List[dict]
    ) -> List[TimelineDocument]:
        """Create `TimelineDocument` instances from processed document dictionaries."""

        mapped = [self._map_processed_document(doc) for doc in documents]
        documents_as_models = [self._normalize_document(doc) for doc in mapped]
        return sorted(
            documents_as_models,
            key=lambda doc: doc.created_at or datetime.min,
        )

    def _map_processed_document(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize keys from processed documents before model creation."""
        identifier = raw.get("doc_identifier") or raw.get("id")
        if not identifier:
            fallback_source = (
                raw.get("title")
                or raw.get("publisher_link")
                or raw.get("document_link")
                or repr(raw)
            )
            identifier = hashlib.md5(fallback_source.encode("utf-8")).hexdigest()
        return {
            "id": identifier,
            "title": raw.get("title", "Onbekend document"),
            "created_at": raw.get("created_at"),
            "publisher": raw.get("publisher"),
            "summary": raw.get("summary"),
            "publisher_link": raw.get("publisher_link"),
            "content_text": raw.get("content_text") or [],
            "informatieobject": raw.get("informatieobject") or {},
        }

    def _normalize_timeline(
        self, timeline: TimelineModel | dict[str, Any]
    ) -> TimelineModel:
        """Ensure the timeline and nested documents are model instances."""
        if isinstance(timeline, dict):
            model = TimelineModel.from_dict(timeline)
        elif isinstance(timeline, TimelineModel):
            model = timeline
        else:
            raise TypeError(f"Unsupported timeline payload: {type(timeline)!r}")

        model.documents = [
            self._normalize_document(doc) for doc in getattr(model, "documents", [])
        ]
        return model

    def _normalize_document(
        self, document: TimelineDocument | dict[str, Any]
    ) -> TimelineDocument:
        """Coerce raw dictionaries into TimelineDocument instances."""
        if isinstance(document, dict):
            payload = (
                self._map_processed_document(document)
                if "doc_identifier" in document and "id" not in document
                else document
            )
            model = TimelineDocument.from_dict(payload)
        elif isinstance(document, TimelineDocument):
            model = document
        else:
            raise TypeError(f"Unsupported document payload: {type(document)!r}")

        model.content_text = self._normalize_chunks(model.content_text or [])
        return model

    def _normalize_chunks(self, chunks: Sequence[Any]) -> List[ContentChunk]:
        """Convert stored chunk structures into ContentChunk models."""
        normalized: List[ContentChunk] = []
        for chunk in chunks or []:
            normalized_chunk = self._normalize_chunk(chunk)
            if normalized_chunk is not None:
                normalized.append(normalized_chunk)
        return normalized

    def _normalize_chunk(self, chunk: Any) -> ContentChunk | None:
        """Convert a chunk payload into a ContentChunk model."""
        if chunk is None:
            return None
        if isinstance(chunk, ContentChunk):
            return chunk
        if isinstance(chunk, dict):
            return ContentChunk.from_dict(chunk)
        if isinstance(chunk, str):
            chunk_id = hashlib.md5(chunk.encode("utf-8")).hexdigest()
            return ContentChunk(chunk_identifier=chunk_id, content=chunk)
        return None

    def _refresh_timeline_description(self, tijdlijn: TimelineModel) -> None:
        """Regenerate the overarching timeline description based on document summaries."""
        summaries = [doc.summary for doc in tijdlijn.documents if doc.summary]
        if not summaries:
            tijdlijn.beschrijving = None
            return

        tijdlijn.beschrijving = self.client.generate_description(
            desc_title=tijdlijn.name,
            list_summaries=summaries,
        )

    def _get_search_input(self) -> dict:
        """
        Prompt the user for search terms and document types.

        Returns a dictionary with:
        - "search_terms": list of input keywords
        - "document_type": list of selected document types (defaults to "Alle parlementaire documenten")
        """

        search_terms_input = input(
            "Voer een of meerdere zoektermen in, gescheiden door komma's. Bijvoorbeeld: Box 3 beslisnota, Sparen.\n"
        )
        search_terms = [
            term.strip() for term in search_terms_input.split(",") if term.strip()
        ]

        print("\nBeschikbare document types:")
        for idx, dt in enumerate(AVAILABLE_DOCUMENT_TYPES, start=1):
            print(f"{idx}. {dt}")

        document_type_input = input(
            "\nVoer een of meerdere nummers in van de document types die je wilt gebruiken, gescheiden door komma's: "
        )
        selected_indices = [
            int(i.strip()) - 1
            for i in document_type_input.split(",")
            if i.strip().isdigit()
        ]

        print("\nZoeken naar documenten...")

        document_type = [
            AVAILABLE_DOCUMENT_TYPES[i]
            for i in selected_indices
            if 0 <= i < len(AVAILABLE_DOCUMENT_TYPES)
        ]

        if not document_type:
            print(
                "Geen geldig document type geselecteerd. Gebruik standaard: Alle parlementaire documenten."
            )
            document_type = ["Alle parlementaire documenten"]

        return {"search_terms": search_terms, "document_type": document_type}

    def _get_summary_input(self) -> str | None:
        """
        Prompt the user to select a timeline to summarize.

        Displays all available timelines and asks the user to choose one by number.
        """

        all_timelines = self.repo.find_all()
        if not all_timelines:
            print("Geen timelines gevonden.")
            return None

        print("Beschikbare timelines:")
        for idx, timeline in enumerate(all_timelines, start=1):
            print(f"{idx}. {timeline.name} (id: {timeline.identifier})")

        selected_input = input(
            "Voer het nummer van de timeline in die je wilt samenvatten: "
        ).strip()
        if not selected_input.isdigit() or not (
            1 <= int(selected_input) <= len(all_timelines)
        ):
            print("Ongeldige selectie.")
            return None

        return all_timelines[int(selected_input) - 1].identifier

    def _get_single_doc_input(self, tijdlijn: TimelineModel) -> str | None:
        """
        Ask the user whether to summarize all documents or just one.

        If one document is chosen, display a list of available documents with their titles
        and prompt the user to select one. Returns the document ID.
        """

        docs = tijdlijn.documents
        count = len(docs)

        if count == 0:
            print("Deze tijdlijn bevat geen documenten.")
            return None

        print(f"\nDeze tijdlijn bevat {count} documenten.")
        print("Kies een optie:")
        print("1. Alle documenten samenvatten")
        print("2. Slechts een document samenvatten")

        choice = input("Uw keuze [1/2]: ").strip()

        if choice == "2":
            print("\nBeschikbare documenten:")
            for idx, doc in enumerate(docs, start=1):
                title = doc.title or "Naamloos"
                print(f"{idx}. {title} (id: {doc.id})")

            selected_input = input(
                "\nVoer het nummer in van het document dat u wilt samenvatten: "
            ).strip()
            if not selected_input.isdigit() or not (1 <= int(selected_input) <= count):
                print("Ongeldige selectie.")
                return None

            return docs[int(selected_input) - 1].id

        # Default: alle documenten
        return None

    def _update_single_doc_summary(
        self, tijdlijn: TimelineModel, doc_id: str
    ) -> TimelineModel:
        """Update the summary of a single document within a timeline."""
        print("samenvatten...")

        tijdlijn = self._normalize_timeline(tijdlijn)
        document = tijdlijn.doc_by_id(doc_id)
        if document is None:
            print(f"Document {doc_id} niet gevonden in tijdlijn {tijdlijn.identifier}")
            return tijdlijn

        summary = self.client.generate_doc_summary(document.to_dict(), tijdlijn.name)
        document.summary = summary

        tijdlijn.gegenereerd_op = datetime.now()
        self._refresh_timeline_description(tijdlijn)
        return tijdlijn

    def _update_all_summaries(self, tijdlijn: TimelineModel) -> TimelineModel:
        """Update summaries for all documents within a timeline."""
        tijdlijn = self._normalize_timeline(tijdlijn)
        title = tijdlijn.name

        for document in tqdm(tijdlijn.documents, desc="Samenvatten", unit="doc"):
            summary = self.client.generate_doc_summary(
                doc=document.to_dict(), tijdlijn_title=title
            )
            document.summary = summary

        tijdlijn.gegenereerd_op = datetime.now()
        self._refresh_timeline_description(tijdlijn)
        return tijdlijn

