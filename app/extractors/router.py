import re
from typing import Optional
from app.extractors.base import BaseExtractor
from app.extractors.youtube import YouTubeExtractor
from app.extractors.web import WebExtractor
from app.extractors.social import SocialMediaExtractor


class LinkRouter:
    """Intelligent router selecting the appropriate extraction strategy based on URL domain."""

    SOCIAL_DOMAINS_REGEX = re.compile(
        r"(?:https?://)?(?:www\.)?(?:instagram\.com|twitter\.com|x\.com|linkedin\.com|tiktok\.com)",
        re.IGNORECASE,
    )

    def __init__(self):
        self.youtube_extractor = YouTubeExtractor()
        self.web_extractor = WebExtractor()
        self.social_extractor = SocialMediaExtractor()

    def get_extractor(self, url: str, source_type: Optional[str] = None) -> BaseExtractor:
        """Determines extraction strategy based on URL pattern or optional explicit source_type."""
        if source_type:
            st = source_type.lower()
            if st == "youtube":
                return self.youtube_extractor
            elif st in ("social", "instagram", "twitter", "x", "linkedin", "tiktok"):
                return self.social_extractor
            elif st == "web":
                return self.web_extractor

        # Auto-detect from URL
        if YouTubeExtractor.extract_video_id(url):
            return self.youtube_extractor

        if self.SOCIAL_DOMAINS_REGEX.search(url):
            return self.social_extractor

        return self.web_extractor


link_router = LinkRouter()
