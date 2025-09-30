import os
import hashlib
import requests
from datetime import datetime
from tqdm import tqdm
from ..services.parser import DocumentParser


class DocumentProcessor:
    """Downloads documents, extracts text with DocumentParser, and enriches with metadata."""

    def __init__(self, tmp_file: str = "temp_download.pdf"):
        """
        Initializes the processor with a temporary file path for downloads.

        :param tmp_file:
            Local path where downloaded files will be stored temporarily
        """
        self.tmp_file = tmp_file

    def process(self, documents: list[dict]) -> list[dict]:
        """Processes a list of documents and returns structured results.

        :param documents:
            List of document metadata dicts (must include `document_link`)

        :returns:
            A list of processed document objects, ready for indexing
        :rtype: list[dict]
        """
        documents_to_add = []

        for doc in tqdm(documents, desc="Verwerken", unit="doc"):
            processed = self._process_single(doc)
            if processed:
                documents_to_add.append(processed)

        return documents_to_add

    def _process_single(self, doc: dict) -> dict | None:
        """Processes a single document: downloads, parses, and enriches with metadata.

        :param doc:
            Document metadata dictionary

        :returns:
            Processed document object with extracted content and metadata
        :rtype: dict | None

        :raises requests.RequestException:
            If the document could not be downloaded
        """
        download_url = doc.get("document_link")
        if not download_url:
            return None

        publisher_link = doc.get("publisher_link")
        metadata = doc.get("metadata", {}).get("informatieobject", {})

        file_path = self._download_file(download_url)
        try:
            parser = DocumentParser(file_path)

            if not parser.content:
                return None

            chunks = parser.chunk_text(
                parser.content, chunk_size=4000, chunk_overlap=200
            )
            title, published, author = self._parse_metadata(metadata)
            doc_identifier = self._generate_doc_identifier(title)

            return {
                "content_text": chunks,
                "title": title,
                "doc_identifier": doc_identifier,
                "created_at": published,
                "publisher": author,
                "publisher_link": publisher_link,
                "informatieobject": metadata,
            }
        finally:
            os.remove(file_path)

    def _download_file(self, url: str) -> str:
        """Downloads a file from a given URL to the temporary file path.

        :param url:
            URL to the file

        :returns:
            Local path to the downloaded file
        :rtype: str

        :raises requests.RequestException:
            If the download request fails
        """
        response = requests.get(url)
        response.raise_for_status()
        with open(self.tmp_file, "wb") as f:
            f.write(response.content)
        return self.tmp_file

    def _parse_metadata(self, metadata: dict) -> tuple[str, str, str]:
        """Extracts title, publication date, and author from metadata.

        :param metadata:
            Metadata dictionary of the document

        :returns:
            Tuple containing (title, published date, author)
        :rtype: tuple[str, str, str]
        """
        title = metadata.get("titel", "Onbekend document")  # DC.title
        published_raw = metadata.get(
            "beschikbaarVanaf", datetime.now().strftime("%Y-%m-%d")
        )  # DCTERMS.available
        published = datetime.strptime(
            published_raw, "%Y-%m-%d"
        ).strftime("%Y-%m-%d %H:%M:%S")
        author = metadata.get("organisatie", {}).get("naam", "Onbekend")  # DC.creator
        return title, published, author

    def _generate_doc_identifier(self, title: str) -> str:
        """Generates a stable identifier for a document based on its title.

        :param title:
            Document title

        :returns:
            MD5 hash string of the title
        :rtype: str
        """
        return hashlib.md5(title.encode("utf-8")).hexdigest()
