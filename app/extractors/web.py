import re
import httpx
from typing import Optional
from app.extractors.base import BaseExtractor
from app.schemas.ingestion import ExtractedContent
from app.core.exceptions import ExtractionError, RateLimitError
from app.core.logging import logger
from app.core.config import settings


class WebExtractor(BaseExtractor):
    """General Web Article Extractor using Jina Reader API (https://r.jina.ai/) with HTTP fallback."""

    JINA_READER_PREFIX = "https://r.jina.ai/"

    async def extract(self, url: str) -> ExtractedContent:
        self.validate_url_access(url)
        logger.info("Extracting web article via Jina Reader API", target_url=url)

        jina_url = f"{self.JINA_READER_PREFIX}{url}"
        headers = {
            "Accept": "application/json",
            "X-With-Generated-Alt": "true",
        }
        if settings.JINA_API_KEY:
            headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(jina_url, headers=headers)

                if response.status_code == 429:
                    retry_after_str = response.headers.get("Retry-After", "60")
                    retry_after = int(retry_after_str) if retry_after_str.isdigit() else 60
                    self.record_failure(url, is_block_or_rate_limit=True)
                    raise RateLimitError(f"Rate limited by Jina API for {url}", retry_after=retry_after)

                if response.status_code == 200:
                    data = response.json() if "application/json" in response.headers.get("Content-Type", "") else {}
                    content_text = data.get("data", {}).get("content") or response.text
                    title = data.get("data", {}).get("title") or self._extract_title_from_url(url)
                    author = data.get("data", {}).get("author") or "Web Page"

                    self.record_success(url)
                    return ExtractedContent(
                        raw_text=content_text,
                        title=title,
                        author=author,
                        metadata={"extractor": "JinaReader", "status_code": 200},
                        source_url=url,
                    )

                logger.warning("Jina Reader API returned non-200. Attempting direct HTML HTTP fallback.", status_code=response.status_code)
                return await self._fallback_direct_fetch(url)

        except (RateLimitError, ExtractionError):
            raise
        except Exception as exc:
            logger.warning("Jina Reader API failed. Executing direct HTTP fallback", error=str(exc))
            return await self._fallback_direct_fetch(url)

    async def _fallback_direct_fetch(self, url: str) -> ExtractedContent:
        """Direct HTTP GET fallback using httpx."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        proxy = settings.PROXY_URL if settings.PROXY_URL else None

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, proxy=proxy) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 429:
                    retry_after_str = resp.headers.get("Retry-After", "60")
                    retry_after = int(retry_after_str) if retry_after_str.isdigit() else 60
                    self.record_failure(url, is_block_or_rate_limit=True)
                    raise RateLimitError(f"Rate limited by target site {url}", retry_after=retry_after)

                if resp.status_code in (403, 401):
                    self.record_failure(url, is_block_or_rate_limit=True)
                    raise ExtractionError(f"Access forbidden (HTTP {resp.status_code}) for target site {url}")

                resp.raise_for_status()

                # Basic HTML cleaning / text extraction fallback
                raw_html = resp.text
                clean_text = self._strip_html_tags(raw_html)
                title = self._extract_title_from_html(raw_html) or self._extract_title_from_url(url)

                self.record_success(url)
                return ExtractedContent(
                    raw_text=clean_text,
                    title=title,
                    author="Web Author",
                    metadata={"extractor": "DirectHTTPFallback", "status_code": resp.status_code},
                    source_url=url,
                )
        except (RateLimitError, ExtractionError):
            raise
        except Exception as exc:
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Direct web extraction failed for {url}: {str(exc)}")

    def _strip_html_tags(self, html: str) -> str:
        # Remove scripts, styles and HTML tags
        html_clean = re.sub(r"<(script|style).*?>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html_clean)
        return re.sub(r"\s+", " ", text).strip()

    def _extract_title_from_html(self, html: str) -> Optional[str]:
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None

    def _extract_title_from_url(self, url: str) -> str:
        cleaned = url.split("://")[-1].rstrip("/")
        return cleaned.split("/")[-1] or cleaned
