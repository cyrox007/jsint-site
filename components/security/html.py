from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from markupsafe import Markup


_ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "blockquote", "pre", "code", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "a", "img",
}
_VOID_TAGS = {"br", "img"}
_DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "svg", "math"}


def _safe_image_src(value: str) -> str | None:
    value = value.strip()
    if not value or value.startswith("//"):
        return None

    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return None
    return value


def _safe_href(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return None
    if value.startswith("//"):
        return None
    return value


class _RichTextSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in _DROP_WITH_CONTENT:
            self.drop_depth += 1
            return
        if self.drop_depth or tag not in _ALLOWED_TAGS:
            return

        if tag == "br":
            self.parts.append("<br>")
            return

        if tag == "img":
            attr_map = {str(k).lower(): str(v) for k, v in attrs if k and v is not None}
            src = _safe_image_src(attr_map.get("src", ""))
            if src:
                alt = attr_map.get("alt", "").strip()[:500]
                self.parts.append(
                    '<img src="{}" alt="{}" loading="lazy">'.format(
                        escape(src, quote=True),
                        escape(alt, quote=True),
                    )
                )
            return

        if tag == "a":
            attr_map = {str(k).lower(): str(v) for k, v in attrs if k and v is not None}
            href = _safe_href(attr_map.get("href", ""))
            if href:
                self.parts.append(
                    '<a href="{}" rel="noopener noreferrer nofollow">'.format(
                        escape(href, quote=True)
                    )
                )
                return

        self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _DROP_WITH_CONTENT:
            if self.drop_depth:
                self.drop_depth -= 1
            return
        if self.drop_depth or tag not in _ALLOWED_TAGS or tag in _VOID_TAGS:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self.drop_depth:
            self.parts.append(escape(data))

    def handle_comment(self, data: str) -> None:
        return


def sanitize_rich_text(value: str | None) -> str:
    parser = _RichTextSanitizer()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.parts)


def safe_rich_text(value: str | None) -> Markup:
    return Markup(sanitize_rich_text(value))
