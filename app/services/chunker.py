"""
Semantic Chunking Service — Intelligent text splitting with metadata injection.

Strategy (per skill 11 - Advanced Semantic Chunking):
  1. Split by semantic boundaries (headings, paragraphs, sentences) instead of
     hard character limits that break mid-sentence.
  2. Inject document metadata (title, author) into each chunk header so the
     embedding vector captures document-level context.
  3. Clean final output: collapse excessive newlines / spaces to maximize
     useful tokens sent to the embedding provider.

Reference: skills/11-advanced-semantic-chunking.md
"""

import re
from typing import List, Dict, Any, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.core.logging import logger


# ── Sentence-level separators (ordered from strongest to weakest boundary) ───
_SEMANTIC_SEPARATORS = [
    "\n## ",       # Markdown H2 heading (strong topic boundary)
    "\n### ",      # Markdown H3 heading
    "\n# ",        # Markdown H1 heading
    "\n\n",        # Paragraph break (natural semantic boundary)
    "\n",          # Single newline (soft boundary)
    ". ",          # End of sentence (period + space)
    "? ",          # End of question
    "! ",          # End of exclamation
    "; ",          # Semicolon (clause boundary)
    ", ",          # Comma (weak clause boundary)
    " ",           # Word boundary (last resort before char split)
    "",            # Character-level split (absolute fallback)
]


class ChunkingService:
    """Splits text into semantically coherent, metadata-enriched chunks for vector search."""

    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=_SEMANTIC_SEPARATORS,
            keep_separator=True,
        )

    def create_chunks(
        self,
        text: str,
        document_title: str = "Untitled",
        document_author: str = "Unknown",
    ) -> List[Dict[str, Any]]:
        """
        Split text into semantically coherent chunks with metadata headers.

        Args:
            text: The cleaned markdown text to chunk.
            document_title: Title of the source document (injected into chunk header).
            document_author: Author of the source document (injected into chunk header).

        Returns:
            List of dicts with 'chunk_index' and 'chunk_text' keys.
        """
        if not text:
            return []

        # 1. Strip YAML frontmatter before chunking (it's metadata, not content)
        content = self._strip_frontmatter(text)
        if not content.strip():
            return []

        # 2. Split using semantic separators
        raw_chunks = self.splitter.split_text(content)

        # 3. Build enriched chunk records
        metadata_header = self._build_metadata_header(document_title, document_author)
        chunk_records: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(raw_chunks):
            # Clean chunk text before enrichment
            clean_chunk = self._clean_chunk_text(chunk)
            if not clean_chunk:
                continue

            # Inject metadata header (skill 11 §2)
            enriched_text = f"{metadata_header}\n{clean_chunk}"

            chunk_records.append(
                {
                    "chunk_index": idx,
                    "chunk_text": enriched_text,
                }
            )

        logger.debug(
            "Semantic chunking completed",
            total_chunks=len(chunk_records),
            document_title=document_title,
        )
        return chunk_records

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _build_metadata_header(title: str, author: str) -> str:
        """
        Build the metadata header injected at the top of each chunk.

        Format per skill 11:
            [Documento: Título do Artigo]
            [Autor: Nome]
        """
        return f"[Documento: {title}]\n[Autor: {author}]"

    @staticmethod
    def _strip_frontmatter(text: str) -> str:
        """Remove YAML frontmatter (--- ... ---) from the beginning of the text."""
        if text.startswith("---"):
            end_marker = text.find("---", 3)
            if end_marker != -1:
                return text[end_marker + 3:].strip()
        return text

    @staticmethod
    def _clean_chunk_text(chunk: str) -> str:
        """
        Final cleanup per skill 11 §3:
          - Collapse 3+ consecutive newlines into 2.
          - Collapse multiple spaces into single space.
          - Strip leading/trailing whitespace.
        """
        # Collapse triple+ newlines → double newline
        cleaned = re.sub(r"\n{3,}", "\n\n", chunk)
        # Collapse multiple spaces → single space (per line)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        # Strip
        cleaned = cleaned.strip()
        return cleaned
