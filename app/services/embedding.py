import httpx
import math
from typing import List
from app.core.config import settings
from app.core.logging import logger


class EmbeddingService:
    """Generates text embeddings using OpenAI API (text-embedding-3-small) with mock fallback."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self.api_key:
            try:
                return await self._openai_embedding_request(texts)
            except Exception as exc:
                logger.error("OpenAI embedding API call failed. Using deterministic mock fallback", error=str(exc))
                return [self._mock_embedding(t) for t in texts]
        else:
            logger.info("OpenAI API Key not present. Utilizing deterministic mock embedding generator")
            return [self._mock_embedding(t) for t in texts]

    async def generate_query_embedding(self, query: str) -> List[float]:
        embeddings = await self.generate_embeddings([query])
        return embeddings[0] if embeddings else self._mock_embedding(query)

    async def _openai_embedding_request(self, texts: List[str]) -> List[List[float]]:
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": self.model,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    def _mock_embedding(self, text: str) -> List[float]:
        """Generates a normalized deterministic mock vector based on string hash for testing."""
        vec = []
        seed = sum(ord(c) for c in text)
        for i in range(self.dimension):
            val = math.sin(seed + i)
            vec.append(val)
        # Normalize vector
        magnitude = math.sqrt(sum(v * v for v in vec))
        return [v / magnitude for v in vec] if magnitude > 0 else vec
