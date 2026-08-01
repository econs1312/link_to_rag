import httpx
from app.extractors.base import BaseExtractor
from app.schemas.ingestion import ExtractedContent
from app.core.exceptions import ExtractionError, RateLimitError
from app.core.logging import logger
from app.core.config import settings


class SocialMediaExtractor(BaseExtractor):
    """Extractor strategy for Instagram, X (Twitter), LinkedIn, and TikTok posts."""

    async def extract(self, url: str) -> ExtractedContent:
        self.validate_url_access(url)
        logger.info("Extracting social media post content", target_url=url)

        if settings.APIFY_API_TOKEN:
            return await self._extract_via_apify(url)
        else:
            return await self._extract_via_http_fallback(url)

    async def _extract_via_apify(self, url: str) -> ExtractedContent:
        logger.info("Calling Apify API for social media post extraction", target_url=url)
        try:
            # Apify SDK / API invocation simulation
            self.record_success(url)
            return ExtractedContent(
                raw_text=f"[Conteúdo extraído via Apify da postagem: {url}]",
                title="Social Media Post",
                author="Social Author",
                metadata={"platform": "social_media", "extractor": "apify"},
                source_url=url,
            )
        except Exception as exc:
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Apify social extraction failed for {url}: {str(exc)}")

    async def _extract_via_http_fallback(self, url: str) -> ExtractedContent:
        logger.info("Using HTTP fallback for social media post extraction", target_url=url)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 429:
                    self.record_failure(url, is_block_or_rate_limit=True)
                    raise RateLimitError(f"Rate limited by social platform {url}", retry_after=60)

                self.record_success(url)
                return ExtractedContent(
                    raw_text=f"[Postagem social capturada via HTTP GET: {url}]",
                    title="Social Post",
                    author="Social Media Account",
                    metadata={"platform": "social_media", "extractor": "http_fallback"},
                    source_url=url,
                )
        except RateLimitError:
            raise
        except Exception as exc:
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Social HTTP extraction failed for {url}: {str(exc)}")
