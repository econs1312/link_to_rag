import re
import yaml
from datetime import datetime, timezone
from app.schemas.ingestion import ExtractedContent


class TextCleanerService:
    """Sanitizes text, normalizes whitespace, formats Markdown structure and prepends YAML Frontmatter."""

    @classmethod
    def clean_text(cls, raw_text: str) -> str:
        if not raw_text:
            return ""

        # 1. Remove residual HTML tags
        text = re.sub(r"<[^>]+>", " ", raw_text)

        # 2. Normalize carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Replace multiple inline spaces with single space
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

        # 4. Remove more than two consecutive newlines
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()

    @classmethod
    def format_with_frontmatter(cls, content: ExtractedContent, cleaned_text: str) -> str:
        frontmatter_dict = {
            "title": content.title,
            "source_url": content.source_url,
            "author": content.author,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        if content.metadata:
            frontmatter_dict.update(content.metadata)

        yaml_str = yaml.dump(frontmatter_dict, sort_keys=False, allow_unicode=True).strip()

        formatted_markdown = f"---\n{yaml_str}\n---\n\n{cleaned_text}"
        return formatted_markdown
