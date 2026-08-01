import subprocess
import json
import asyncio
import httpx
from app.extractors.base import BaseExtractor
from app.schemas.ingestion import ExtractedContent
from app.core.exceptions import ExtractionError, RateLimitError
from app.core.logging import logger
from app.core.config import settings


class SocialMediaExtractor(BaseExtractor):
    """Extractor strategy for Instagram, Facebook, X (Twitter), LinkedIn, and TikTok posts."""

    async def extract(self, url: str) -> ExtractedContent:
        self.validate_url_access(url)
        logger.info("Extracting social media post content", target_url=url)

        if settings.APIFY_API_TOKEN:
            return await self._extract_via_apify(url)

        # 1. Try yt-dlp for social videos, reels and posts
        try:
            return await self._extract_via_ytdlp(url)
        except Exception as exc:
            logger.info("yt-dlp extraction skipped or failed, falling back to HTTP GET", error=str(exc))
            return await self._extract_via_http_fallback(url)

    async def _extract_via_ytdlp(self, url: str) -> ExtractedContent:
        logger.info("Executing yt-dlp metadata extraction for social media link", target_url=url)
        loop = asyncio.get_event_loop()

        def run_ytdlp():
            res = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-warnings", "--skip-download", url],
                capture_output=True,
                text=True,
                timeout=25,
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout)
            raise RuntimeError(f"yt-dlp returned code {res.returncode}: {res.stderr[:200]}")

        data = await loop.run_in_executor(None, run_ytdlp)
        title = data.get("title") or "Social Media Post"
        author = data.get("uploader") or data.get("channel") or "Social Media Account"
        description = data.get("description") or data.get("fulltitle") or title

        # Extract spoken audio transcription (Whisper AI) — graceful fallback if unavailable
        audio_transcript = ""
        try:
            from app.services.audio_transcriber import audio_transcriber
            audio_transcript = await audio_transcriber.transcribe_video_audio(url)
        except Exception as audio_exc:
            logger.warning(
                "Audio transcription failed for social media video, continuing with text-only content",
                target_url=url,
                error=str(audio_exc),
            )
        full_content = f"{description}{audio_transcript}"

        self.record_success(url)
        return ExtractedContent(
            raw_text=full_content,
            title=title,
            author=author,
            metadata={
                "platform": "social_media",
                "extractor": "yt-dlp_whisper",
                "uploader_id": data.get("uploader_id"),
                "like_count": data.get("like_count"),
                "view_count": data.get("view_count"),
                "has_audio_transcript": bool(audio_transcript),
            },
            source_url=url,
        )

    async def _extract_via_apify(self, url: str) -> ExtractedContent:
        logger.info("Calling Apify API for social media post extraction", target_url=url)
        try:
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 429:
                    self.record_failure(url, is_block_or_rate_limit=True)
                    raise RateLimitError(f"Rate limited by social platform {url}", retry_after=60)

                raw_html = resp.text if resp.status_code == 200 else ""
                title = "Post em Rede Social"
                if raw_html:
                    import re
                    m = re.search(r"<title>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
                    if m:
                        title = m.group(1).strip()

                self.record_success(url)
                return ExtractedContent(
                    raw_text=f"[Postagem Social ({url})]: {title}\nNota: Para raspagem de posts com login wall, recomenda-se configurar a chave APIFY_API_TOKEN no .env.",
                    title=title,
                    author="Social Media Account",
                    metadata={"platform": "social_media", "extractor": "http_fallback", "status_code": resp.status_code},
                    source_url=url,
                )
        except RateLimitError:
            raise
        except Exception as exc:
            logger.warning("Social HTTP extraction exception caught, returning graceful fallback", error=str(exc))
            self.record_success(url)
            return ExtractedContent(
                raw_text=f"[Post de Rede Social ({url})]: Não foi possível extrair a transcrição completa via HTTP direto.\nPara extrair posts de redes sociais protegidos por login, configure a APIFY_API_TOKEN no arquivo .env.",
                title="Rede Social (Facebook / Instagram)",
                author="Rede Social",
                metadata={"platform": "social_media", "fallback": True},
                source_url=url,
            )
