from app.extractors.router import LinkRouter
from app.extractors.youtube import YouTubeExtractor
from app.extractors.social import SocialMediaExtractor
from app.extractors.web import WebExtractor
from tests.fixtures.sample_responses import SAMPLE_YOUTUBE_URLS, SAMPLE_SOCIAL_URLS, SAMPLE_WEB_URLS


def test_link_router_youtube():
    router = LinkRouter()
    for url in SAMPLE_YOUTUBE_URLS:
        extractor = router.get_extractor(url)
        assert isinstance(extractor, YouTubeExtractor)


def test_link_router_social():
    router = LinkRouter()
    for url in SAMPLE_SOCIAL_URLS:
        extractor = router.get_extractor(url)
        assert isinstance(extractor, SocialMediaExtractor)


def test_link_router_web():
    router = LinkRouter()
    for url in SAMPLE_WEB_URLS:
        extractor = router.get_extractor(url)
        assert isinstance(extractor, WebExtractor)


def test_link_router_explicit_override():
    router = LinkRouter()
    extractor = router.get_extractor("https://example.com/article", source_type="youtube")
    assert isinstance(extractor, YouTubeExtractor)
