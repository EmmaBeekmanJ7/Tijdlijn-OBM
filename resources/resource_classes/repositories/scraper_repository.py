"""OBM Scraper Repository utilities."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Sequence
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse

import requests
import xmltodict
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace

from resource_classes import DocumentsNotFound
from ..data_models.mdto import (
    Bestand,
    Informatieobject,
    Informatietype,
    MDTO,
    Organisatie,
    OrganisatieType,
    ParlementairType,
    Relatie,
    Taal,
    TechnischeContext,
)
from ..data_models.scraper_models import DocumentSearchResult, RawDocument, SearchQuery

Headers = Dict[str, str]
PageDocumentIndex = Dict[int, List[str]]

BASE_SEARCH_URL = "https://zoek.officielebekendmakingen.nl/resultaten"
PRODUCT_AREA_FILTER = "(c.product-area==%22officielepublicaties%22)"
ALL_PUBLICATIONS_FILTER = (
    "(((w.publicatienaam==%22Agenda%22))or((w.publicatienaam==%22Handelingen%22))"
    "or((w.publicatienaam==%22Kamerstuk%22))or(((w.publicatienaam==%22Kamervragen%20(Aanhangsel)%22)"
    "or(w.publicatienaam==%22Kamervragen%20zonder%20antwoord%22)))or((w.publicatienaam==%22Niet-dossierstuk%22)))"
)
DOCUMENT_TYPE_FRAGMENTS = {
    "handelingen": "((w.publicatienaam==%22Handelingen%22))",
    "motie": "((w.subrubriek==%22motie%22))",
    "kamervragen": "(((w.publicatienaam==%22Kamervragen%20(Aanhangsel)%22)"
    "or(w.publicatienaam==%22Kamervragen%20zonder%20antwoord%22)))",
    "kamerstuk": "((w.publicatienaam==%22Kamerstuk%22))",
    "agenda": "((w.publicatienaam==%22Agenda%22))",
}
PDF_MEDIA_TYPE = {
    "label": "application/pdf",
    "uri": "http://publications.europa.eu/resource/authority/file-type/PDF",
}
METADATA_ENDPOINT_TEMPLATE = "https://zoek.officielebekendmakingen.nl/{document_id}/metadata.xml"
DISPLAY_URL_TEMPLATE = "https://zoek.officielebekendmakingen.nl/{document_id}"
DEFAULT_TIMEOUT = 30

DEFAULT_HEADERS: Headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class PageFetcher:
    """Small HTTP helper to retrieve and parse search result pages."""

    def __init__(self, headers: Headers | None = None, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.headers = headers or DEFAULT_HEADERS
        self.timeout = timeout

    def fetch_html(self, url: str) -> str:
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    @staticmethod
    def parse_html(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")


class ResultParser:
    """Extracts pagination info and document identifiers from a search page."""

    PAGE_QUERY_PATTERN = re.compile(r"[?&]pagina=(\d+)")
    DOCUMENT_ID_PATTERN = re.compile(r"/([^/]+)\.html(?:$|\?)")

    @classmethod
    def detect_total_pages(cls, soup: BeautifulSoup) -> int:
        last_link = soup.select_one('a[rel="last"]')
        if last_link and (href := last_link.get("href")):
            if match := cls.PAGE_QUERY_PATTERN.search(href):
                return int(match.group(1))

        candidates = [
            int(match.group(1))
            for anchor in soup.find_all("a", href=True)
            if (match := cls.PAGE_QUERY_PATTERN.search(anchor["href"]))
        ]
        return max(candidates) if candidates else 1

    @classmethod
    def extract_result_ids(cls, soup: BeautifulSoup, base_url: str) -> List[str]:
        ids: List[str] = []
        for anchor in soup.select("h2.result--title a, h2.result-title a"):
            href = anchor.get("href")
            if not href:
                continue
            abs_url = urljoin(base_url, href)
            if match := cls.DOCUMENT_ID_PATTERN.search(abs_url):
                ids.append(match.group(1))
        return ids


class LabelToUriMapper:
    """Loads Turtle files and resolves SKOS labels to URIs."""

    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

    def __init__(self, ttl_dir: str) -> None:
        self.graph = Graph()
        for fname in os.listdir(ttl_dir):
            if fname.endswith(".ttl"):
                self.graph.parse(os.path.join(ttl_dir, fname), format="turtle")

    def resolve(self, label: str | None) -> str | None:
        if not label:
            return None
        label_lower = label.lower()
        for subject, obj in self.graph.subject_objects(self.SKOS.prefLabel):
            if str(obj).lower() == label_lower:
                return str(subject)
        return None

    def find_uri_by_label(self, label: str | None) -> str | None:
        """Backward compatible wrapper around resolve."""
        return self.resolve(label)


class MetadataRepository:
    """Retrieves metadata XML files and converts them to the MDTO schema."""

    def __init__(self, ttl_dir: str, headers: Headers | None = None, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.resolver = LabelToUriMapper(ttl_dir)
        self.headers = headers or DEFAULT_HEADERS
        self.timeout = timeout

    def fetch(self, document_id: str, display_url: str, document_url: str) -> Dict[str, object]:
        xml_text = self._fetch_metadata_xml(document_id)
        metadata = self._flatten_metadata(xml_text)
        informatieobject = self._build_informatieobject(metadata, display_url, document_url)
        return MDTO(informatieobject=informatieobject).to_dict()

    def _fetch_metadata_xml(self, document_id: str) -> str:
        url = METADATA_ENDPOINT_TEMPLATE.format(document_id=document_id)
        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _flatten_metadata(xml_text: str) -> Dict[str, object]:
        data = xmltodict.parse(xml_text)
        meta_items = data.get("metadata_gegevens", {}).get("metadata", [])
        if isinstance(meta_items, dict):
            meta_items = [meta_items]
        return {
            item["@name"]: item.get("@content")
            for item in meta_items
            if isinstance(item, dict) and "@name" in item
        }

    def _build_informatieobject(
        self,
        metadata: Dict[str, object],
        display_url: str,
        document_url: str,
    ) -> Informatieobject:
        get = metadata.get

        return Informatieobject(
            identificatie=get("DC.identifier"),
            titel=get("DC.title"),
            status=get("OVERHEIDop.documentStatus"),
            informatietype=Informatietype(
                label=get("OVERHEIDop.publicationName"),
                uri=self.resolver.resolve(get("OVERHEIDop.publicationName")),
            ),
            parlementairType=ParlementairType(
                label=get("DC.type"),
                uri=self.resolver.resolve(get("DC.type")),
            ),
            dossierNummer=get("OVERHEIDop.dossiernummer"),
            ondernummer=get("OVERHEIDop.ondernummer"),
            vergaderjaar=get("OVERHEIDop.vergaderjaar"),
            taal=Taal(
                label=get("DCTERMS.language"),
                uri=self.resolver.resolve(get("DCTERMS.language")),
            ),
            beschikbaarVanaf=get("DCTERMS.available"),
            organisatie=Organisatie(
                naam=get("DC.creator"),
                organisatieType=OrganisatieType(
                    label=get("OVERHEID.organisationType"),
                    uri=self.resolver.resolve(get("OVERHEID.organisationType")),
                ),
                uri=self.resolver.resolve(get("DC.creator")),
            ),
            relaties=self._build_relations(metadata),
            bestanden=[
                Bestand(
                    weergaveURL=display_url,
                    documentURL=document_url,
                    bestandsformaat=PDF_MEDIA_TYPE,
                )
            ],
            technischeContext=TechnischeContext(
                configuratieSchema=get("OVERHEIDop.configuratie"),
                doctype=get("OVERHEIDop.doctype"),
            ),
        )

    @staticmethod
    def _build_relations(metadata: Dict[str, object]) -> List[Relatie]:
        relation_target = metadata.get("OVERHEIDop.hoofddocument")
        if not relation_target:
            return []
        return [Relatie(targetIdentificatie=str(relation_target))]


class DocumentRepository:
    """High-level repository that combines search pages and metadata enrichment."""

    def __init__(self, ttl_dir: str, headers: Headers | None = None, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.headers = headers or DEFAULT_HEADERS
        self.timeout = timeout
        self.fetcher = PageFetcher(headers=self.headers, timeout=self.timeout)
        self.metadata_repository = MetadataRepository(ttl_dir, headers=self.headers, timeout=self.timeout)

    def search(self, query: SearchQuery, max_pages: int = 10) -> DocumentSearchResult:
        base_url = self._build_query_url(query.term, query.document_types)
        first_page_soup = self._fetch_page(base_url)
        total_pages = ResultParser.detect_total_pages(first_page_soup)

        documents: List[RawDocument] = []
        page_document_ids: PageDocumentIndex = {}

        for page_number in self._iterate_pages(total_pages, max_pages):
            doc_ids = self._fetch_document_ids(base_url, page_number)
            page_document_ids[page_number] = doc_ids
            documents.extend(self._collect_documents(doc_ids))

        return DocumentSearchResult(
            query=query,
            documents=documents,
            total_pages=total_pages,
            page_document_ids=page_document_ids,
        )

    def _fetch_page(self, url: str) -> BeautifulSoup:
        html = self.fetcher.fetch_html(url)
        return self.fetcher.parse_html(html)

    def _fetch_document_ids(self, base_url: str, page_number: int) -> List[str]:
        page_url = self._set_page_param(base_url, page_number)
        soup = self._fetch_page(page_url)
        return ResultParser.extract_result_ids(soup, page_url)

    def _collect_documents(self, document_ids: Sequence[str]) -> List[RawDocument]:
        selected_ids = self._select_document_ids(document_ids)
        documents: List[RawDocument] = []
        for document_id in selected_ids:
            documents.append(self._build_document(document_id))
        return documents

    def _build_document(self, document_id: str) -> RawDocument:
        display_url = DISPLAY_URL_TEMPLATE.format(document_id=document_id)
        pdf_url = f"{display_url}.pdf"
        try:
            metadata = self.metadata_repository.fetch(document_id, display_url, pdf_url)
        except requests.RequestException as exc:
            raise DocumentsNotFound(
                f"Document {pdf_url} kon niet goed worden gescraped."
            ) from exc

        return RawDocument(
            publisher_link=display_url,
            document_link=pdf_url,
            metadata=metadata,
        )

    @staticmethod
    def _select_document_ids(document_ids: Sequence[str]) -> List[str]:
        return list(document_ids)

    @staticmethod
    def _iterate_pages(total_pages: int, max_pages: int) -> range:
        last_page = min(total_pages, max_pages) if max_pages else total_pages
        return range(1, last_page + 1)

    @staticmethod
    def _set_page_param(url: str, page_number: int) -> str:
        parts = urlparse(url)
        query = parse_qs(parts.query)
        query["pagina"] = [str(page_number)]
        return urlunparse(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                parts.params,
                urlencode(query, doseq=True),
                parts.fragment,
            )
        )

    def _build_query_url(self, term: str, document_types: List[str]) -> str:
        title_filter = self._build_title_filter(term)
        publication_filter = self._determine_publication_filter(document_types)
        query = "and".join([
            PRODUCT_AREA_FILTER,
            publication_filter,
            f"({title_filter})",
        ])
        return f"{BASE_SEARCH_URL}?q={query}"

    @staticmethod
    def _build_title_filter(term: str) -> str:
        tokens = [token for token in re.split(r"\s+", term.strip()) if token]
        if not tokens:
            return "dt.title=%22%22"
        encoded_tokens = [quote(token, safe="") for token in tokens]
        return "%20and%20".join(f"dt.title=%22{token}%22" for token in encoded_tokens)

    def _determine_publication_filter(self, document_types: List[str]) -> str:
        normalized = [doc_type.lower() for doc_type in document_types]
        if not normalized or "alle parlementaire documenten" in normalized:
            return ALL_PUBLICATIONS_FILTER

        selected_fragments = [
            fragment
            for key, fragment in DOCUMENT_TYPE_FRAGMENTS.items()
            if any(key in doc_type for doc_type in normalized)
        ]

        if not selected_fragments:
            raise DocumentsNotFound("Geen geldige document types geselecteerd voor scraping.")

        if len(selected_fragments) == 1:
            return selected_fragments[0]

        return "(" + "or".join(selected_fragments) + ")"
