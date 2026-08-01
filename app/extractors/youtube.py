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

    def _fetch_transcript_sync(self, video_id: str) -> list[str]:
        api = YouTubeTranscriptApi()
        try:
            if hasattr(api, "fetch"):
                snippets = api.fetch(video_id, languages=["pt", "en", "es"])
                return [s.text if hasattr(s, "text") else s.get("text", "") for s in snippets]
            elif hasattr(YouTubeTranscriptApi, "get_transcript"):
                snippets = YouTubeTranscriptApi.get_transcript(video_id, languages=["pt", "en", "es"])
                return [s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "") for s in snippets]
            else:
                snippets = api.fetch(video_id)
                return [s.text if hasattr(s, "text") else s.get("text", "") for s in snippets]
        except Exception as lang_exc:
            # Fallback to fetch without language constraint if language matching fails
            logger.debug("Language-constrained transcript fetch failed, retrying without language filter", video_id=video_id, error=str(lang_exc))
            snippets = api.fetch(video_id)
            return [s.text if hasattr(s, "text") else s.get("text", "") for s in snippets]

    async def extract(self, url: str) -> ExtractedContent:
        self.validate_url_access(url)
        video_id = self.extract_video_id(url)
        if not video_id:
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Invalid YouTube URL: {url}")

        logger.info("Extracting YouTube video transcript", video_id=video_id, target_url=url)

        try:
            loop = asyncio.get_event_loop()
            transcript_texts = await loop.run_in_executor(
                None, lambda: self._fetch_transcript_sync(video_id)
            )

            full_text = "\n".join(transcript_texts)
            self.record_success(url)

            return ExtractedContent(
                raw_text=full_text,
                title=f"YouTube Video ({video_id})",
                author="YouTube Channel",
                metadata={"video_id": video_id, "platform": "youtube", "has_transcript": True},
                source_url=url,
            )

        except (TranscriptsDisabled, NoTranscriptFound) as exc:
            logger.warning(
                "Transcript disabled or not found, falling back to Whisper audio transcription",
                video_id=video_id,
                reason=str(exc),
            )
            return await self._whisper_fallback(video_id, url)
        except Exception as exc:
            logger.error("YouTube transcript extraction failed", video_id=video_id, error=str(exc))
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Failed to extract YouTube transcript for {video_id}: {str(exc)}")

    async def _whisper_fallback(self, video_id: str, url: str) -> ExtractedContent:
        """Fallback method utilizing yt-dlp to extract audio and OpenAI Whisper API if configured."""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API Key not configured for Whisper fallback. Returning placeholder.", video_id=video_id)
            self.record_success(url)
            return ExtractedContent(
                raw_text=f"[Transcrições desabilitadas para o vídeo YouTube {video_id}. Para transcrição automática via Whisper, configure a OPENAI_API_KEY no arquivo .env]",
                title=f"YouTube Video ({video_id})",
                author="YouTube Channel",
                metadata={"video_id": video_id, "platform": "youtube", "fallback_used": "none", "has_transcript": False},
                source_url=url,
            )

        try:
            logger.info("Executing yt-dlp + OpenAI Whisper audio transcription fallback", video_id=video_id)
            from app.services.audio_transcriber import audio_transcriber
            whisper_text = await audio_transcriber.transcribe_video_audio(url)

            self.record_success(url)
            return ExtractedContent(
                raw_text=whisper_text or f"[Transcrição de áudio não disponível para o vídeo {video_id}]",
                title=f"YouTube Video ({video_id})",
                author="YouTube Channel",
                metadata={
                    "video_id": video_id,
                    "platform": "youtube",
                    "fallback_used": "whisper",
                    "has_transcript": bool(whisper_text),
                },
                source_url=url,
            )
        except Exception as exc:
            logger.error("Whisper fallback failed for YouTube video", video_id=video_id, error=str(exc))
            self.record_failure(url, is_block_or_rate_limit=False)
            raise ExtractionError(f"Whisper fallback failed for YouTube video {video_id}: {str(exc)}")

