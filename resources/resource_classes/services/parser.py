import hashlib
import os
import re

from pdfminer.high_level import extract_text as extract_pdf_text
from langchain.text_splitter import RecursiveCharacterTextSplitter
from docx import Document

class DocumentParser:
    """
    Parses documents and extracts text content for downstream processing.

    """

    def __init__(self, file_path: str):
        """
        Initialize the parser and extract content and metadata from the document.

        :param file_path: Path to the document to parse
        """
        self.file_path = file_path
        parsed_file_attr = self.parseFile(self.file_path)
        content = parsed_file_attr["content"]

        if content:
            # Clean HTML-like tags except anchor tags, normalize whitespace
            self.content = re.sub(
                r"<(?!\/?a(?=>|\s.*>))\/?.*?>",
                " ",
                re.sub(r"\s+", " ", content),
            ).strip()
            self.contentId = self.generate_contentId(self.content)
        else:
            self.content = None
            self.contentId = None

        self.metadata = parsed_file_attr["metadata"]
        self.status = parsed_file_attr["status"]

    @staticmethod
    def parseFile(file_path: str) -> dict:
        """
        Parse a file based on its extension without using external tools like Apache Tika.

        :param file_path: Path to the document file

        :returns: Dictionary containing 'content', 'metadata', and 'status'
        :rtype: dict
        """
        ext = os.path.splitext(file_path)[1].lower()
        content = None
        metadata = {}
        status = "success"

        try:
            if ext == ".pdf":
                content = extract_pdf_text(file_path)
            elif ext == ".docx":
                doc = Document(file_path)
                content = "\n".join([p.text for p in doc.paragraphs])
            elif ext == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                status = f"unsupported file type: {ext}"
        except Exception as e:
            status = f"error parsing file: {str(e)}"

        return {
            "content": content,
            "metadata": metadata,
            "status": status,
        }

    @staticmethod
    def generate_contentId(content: str) -> str:
        """
        Generate a unique identifier (MD5 hash) for a given text content.

        :param content: Text content to hash

        :returns: MD5 hash string representing the content
        :rtype: str
        """
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    @staticmethod
    def chunk_text(content: str, chunk_size: int = 4000, chunk_overlap: int = 200) -> list[dict]:
        """
        Split content into chunks for processing or embedding.

        :param content: Text content to split
        :param chunk_size: Maximum length of each chunk (default: 4000)
        :param chunk_overlap: Number of overlapping characters between consecutive chunks (default: 200)

        :returns: List of dictionaries, each containing a chunk identifier and chunk content
        :rtype: list[dict]
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(chunk_size),
            chunk_overlap=int(chunk_overlap),
            length_function=len,
        )
        
        chunks = splitter.split_text(content)

        chunked_docs = []
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(f"{i}-{chunk}".encode("utf-8")).hexdigest()
            chunked_docs.append({
                "chunk_identifier": chunk_id,
                "content": chunk
            })
        return chunked_docs