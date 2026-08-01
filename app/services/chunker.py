from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings


class ChunkingService:
    """Divides text into optimized overlapping chunks for vector search."""

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
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def create_chunks(self, text: str) -> List[Dict[str, Any]]:
        """Splits text into chunks and returns list of dicts with chunk_index and chunk_text."""
        if not text:
            return []

        raw_chunks = self.splitter.split_text(text)
        chunk_records = []
        for idx, chunk in enumerate(raw_chunks):
            chunk_records.append(
                {
                    "chunk_index": idx,
                    "chunk_text": chunk.strip(),
                }
            )
        return chunk_records
