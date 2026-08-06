import os
import tempfile
import subprocess
import asyncio
import httpx
from app.core.config import settings
from app.core.logging import logger


class AudioTranscriberService:
    """Service for downloading video audio via yt-dlp and transcribing speech to text using OpenAI Whisper API."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY

    async def transcribe_video_audio(self, url: str) -> str:
        """Downloads audio of any video URL (YouTube, Reels, TikTok) and transcribes speech to text."""
        logger.info("Starting audio extraction and Whisper transcription", target_url=url)
        loop = asyncio.get_event_loop()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_template = os.path.join(tmp_dir, "audio.%(ext)s")

            def run_ytdlp_download():
                res = subprocess.run(
                    [
                        "yt-dlp",
                        "-x",
                        "--audio-format",
                        "mp3",
                        "--audio-quality",
                        "5",
                        "-o",
                        output_template,
                        "--no-warnings",
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=settings.YTDLP_TIMEOUT,
                )
                if res.returncode == 0:
                    files = [
                        os.path.join(tmp_dir, f)
                        for f in os.listdir(tmp_dir)
                        if f.endswith((".mp3", ".m4a", ".wav", ".webm", ".aac"))
                    ]
                    return files[0] if files else None
                return None

            audio_file_path = await loop.run_in_executor(None, run_ytdlp_download)
            if not audio_file_path or not os.path.exists(audio_file_path):
                logger.warning("Could not extract audio track via yt-dlp", target_url=url)
                return ""

            if not self.api_key:
                logger.info("Audio track extracted. OPENAI_API_KEY required for Whisper speech-to-text.")
                return "\n\n--- Transcrição de Áudio ---\n[Áudio extraído com sucesso. Para gerar a transcrição automática do que foi falado no vídeo, adicione a OPENAI_API_KEY no arquivo .env]"

            try:
                whisper_text = await self._call_whisper_api(audio_file_path)
                logger.info("Whisper transcription completed successfully", target_url=url)
                return f"\n\n--- Transcrição do Áudio do Vídeo (Whisper AI) ---\n{whisper_text}"
            except Exception as exc:
                logger.error("Whisper transcription API call failed", error=str(exc))
                return ""

    async def _call_whisper_api(self, audio_file_path: str) -> str:
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(audio_file_path, "rb") as f:
                files = {"file": ("audio.mp3", f, "audio/mpeg")}
                data = {"model": "whisper-1"}
                resp = await client.post(url, headers=headers, files=files, data=data)
                resp.raise_for_status()
                res_data = resp.json()
                return res_data.get("text", "").strip()


audio_transcriber = AudioTranscriberService()
