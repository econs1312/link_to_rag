from app.services.text_cleaner import TextCleanerService
from app.schemas.ingestion import ExtractedContent
from tests.fixtures.sample_responses import SAMPLE_RAW_TEXT


def test_text_cleaner_sanitization():
    cleaned = TextCleanerService.clean_text(SAMPLE_RAW_TEXT)
    assert "<script>" not in cleaned
    assert "\n\n\n" not in cleaned
    assert "Retrieval-Augmented Generation" in cleaned


def test_format_with_frontmatter():
    content = ExtractedContent(
        raw_text="Texto simples",
        title="Artigo Exemplo",
        author="Autor Exemplo",
        source_url="https://example.com/test",
    )
    cleaned = TextCleanerService.clean_text(content.raw_text)
    markdown = TextCleanerService.format_with_frontmatter(content, cleaned)

    assert markdown.startswith("---")
    assert 'title: Artigo Exemplo' in markdown or 'title: "Artigo Exemplo"' in markdown
    assert 'source_url: https://example.com/test' in markdown or 'source_url: "https://example.com/test"' in markdown
    assert "Texto simples" in markdown
