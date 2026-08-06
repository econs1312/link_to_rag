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

                # Track 5xx responses as circuit breaker failures
                if response.status_code >= 500:
                    self.record_failure(url, is_block_or_rate_limit=True, status_code=response.status_code)
                logger.warning("Jina Reader API returned non-200. Trying Firecrawl or direct HTTP fallback.", status_code=response.status_code)
                return await self._try_firecrawl_or_direct_fallback(url)

        except (RateLimitError, ExtractionError):
            raise
        except Exception as exc:
            logger.warning("Jina Reader API failed. Trying Firecrawl or direct HTTP fallback", error=str(exc))
            return await self._try_firecrawl_or_direct_fallback(url)

    async def _try_firecrawl_or_direct_fallback(self, url: str) -> ExtractedContent:
        """Try Firecrawl API if configured, otherwise fall back to direct HTTP fetch."""
        if settings.FIRECRAWL_API_KEY:
            try:
                logger.info("Attempting Firecrawl API extraction", target_url=url)
                return await self._extract_via_firecrawl(url)
            except Exception as exc:
                logger.warning("Firecrawl API failed. Falling back to direct HTTP fetch", error=str(exc))
        return await self._fallback_direct_fetch(url)

    async def _extract_via_firecrawl(self, url: str) -> ExtractedContent:
        """Extract content via Firecrawl API (https://api.firecrawl.dev/v1/scrape)."""
        firecrawl_url = "https://api.firecrawl.dev/v1/scrape"
        headers = {
            "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }

        async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
            resp = await client.post(firecrawl_url, json=payload, headers=headers)
            if resp.status_code == 429:
                self.record_failure(url, is_block_or_rate_limit=True)
                raise RateLimitError(f"Rate limited by Firecrawl API for {url}", retry_after=60)

            resp.raise_for_status()
            data = resp.json()

            data_obj = data.get("data", {})
            content_markdown = data_obj.get("markdown") or data_obj.get("content") or ""
            metadata = data_obj.get("metadata", {})
            title = metadata.get("title") or metadata.get("ogTitle") or self._extract_title_from_url(url)
            author = metadata.get("author") or "Web Page"

            self.record_success(url)
            return ExtractedContent(
                raw_text=content_markdown,
                title=title,
                author=author,
                metadata={"extractor": "Firecrawl", "status_code": 200, **metadata},
                source_url=url,
            )


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

                if resp.status_code >= 500:
                    self.record_failure(url, is_block_or_rate_limit=True, status_code=resp.status_code)
                    raise ExtractionError(
                        f"HTTP {resp.status_code} server error fetching {url}: {resp.reason_phrase}"
                    )

                if resp.status_code >= 400:
                    self.record_failure(url, is_block_or_rate_limit=resp.status_code in (429,), status_code=resp.status_code)
                    raise ExtractionError(
                        f"HTTP {resp.status_code} error fetching {url}: {resp.reason_phrase}"
                    )

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
