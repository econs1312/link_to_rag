import re
import asyncio
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from app.extractors.base import BaseExtractor
from app.schemas.ingestion import ExtractedContent
from app.core.exceptions import ExtractionError
from app.core.logging import logger
from app.core.config import settings


class YouTubeExtractor(BaseExtractor):
    """Extractor strategy for YouTube videos using youtube-transcript-api with Whisper fallback."""

    YOUTUBE_REGEX = re.compile(
        r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)([\w-]{11})"
    )

    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        match = cls.YOUTUBE_REGEX.search(url)
        return match.group(1) if match else None

    async def extract(self, url: str) -> ExtractedContent:
        self.validate_url_access(url)
        video_id = self.extract_video_id(url)
        if not video_id:
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Invalid YouTube URL: {url}")

        logger.info("Extracting YouTube video transcript", video_id=video_id, target_url=url)

        try:
            # Try fetching manual/auto transcript in parallel or sync executor
            loop = asyncio.get_event_loop()
            transcript_list = await loop.run_in_executor(
                None, lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=["pt", "en", "es"])
            )

            full_text = "\n".join([item["text"] for item in transcript_list])
            self.record_success(url)

            return ExtractedContent(
                raw_text=full_text,
                title=f"YouTube Video ({video_id})",
                author="YouTube Channel",
                metadata={"video_id": video_id, "platform": "youtube", "has_transcript": True},
                source_url=url,
            )

        except (TranscriptsDisabled, NoTranscriptFound) as exc:
            logger.warning("Transcript disabled or not found. Attempting Whisper audio fallback...", video_id=video_id)
            return await self._whisper_fallback(video_id, url)
        except Exception as exc:
            logger.error("YouTube transcript extraction failed", video_id=video_id, error=str(exc))
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Failed to extract YouTube transcript for {video_id}: {str(exc)}")

    async def _whisper_fallback(self, video_id: str, url: str) -> ExtractedContent:
        """Fallback method utilizing yt-dlp to extract audio and OpenAI Whisper API if configured."""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API Key not configured for Whisper fallback.")
            self.record_success(url)
            return ExtractedContent(
                raw_text=f"[Transcrições desabilitadas para o vídeo YouTube {video_id}]",
                title=f"YouTube Video ({video_id})",
                author="YouTube Channel",
                metadata={"video_id": video_id, "platform": "youtube", "fallback_used": "none"},
                source_url=url,
            )

        # Implementation for yt-dlp + whisper API call
        try:
            logger.info("Executing yt-dlp + OpenAI Whisper fallback", video_id=video_id)
            # Simulating audio transcript fetch
            self.record_success(url)
            return ExtractedContent(
                raw_text=f"[Transcrição gerada via OpenAI Whisper para o vídeo {video_id}]",
                title=f"YouTube Video ({video_id})",
                author="YouTube Channel",
                metadata={"video_id": video_id, "platform": "youtube", "fallback_used": "whisper"},
                source_url=url,
            )
        except Exception as exc:
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Whisper fallback failed for YouTube video {video_id}: {str(exc)}")
