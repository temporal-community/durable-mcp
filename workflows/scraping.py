import re
from html import unescape

# Heavyweight HTML extraction libraries
from bs4 import BeautifulSoup
import trafilatura

# Lightweight fallback regexes
_RE_SCRIPT_STYLE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\\1>")
_RE_TAGS = re.compile(r"(?s)<[^>]+>")
_RE_WS = re.compile(r"\s+")


def _basic_html_to_text(content: str) -> str:
    content = _RE_SCRIPT_STYLE.sub(" ", content)
    content = _RE_TAGS.sub(" ", content)
    content = unescape(content)
    content = _RE_WS.sub(" ", content).strip()
    return content


def html_to_text(content: str) -> str:
    """Extract main textual content from HTML with trafilatura, with BS4 fallback.

    The goal is to avoid boilerplate: scripts, styles, cookie banners, nav, CSS/JS blobs.
    """
    # If content already looks like plain text (no '<' chars), skip heavy HTML cleaning
    if "<" not in content:
        text = content
    else:
        # First choice: trafilatura main content extraction
        try:
            extracted = trafilatura.extract(
                content,
                include_comments=False,
                include_tables=False,
                favor_recall=False,
                no_fallback=False,
                output="txt",
                with_metadata=False,
            )
            if extracted and extracted.strip():
                text = extracted
            else:
                raise ValueError("empty")
        except Exception:
            # Fallback: clean with BeautifulSoup and keep only main/article/body text
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "img", "picture", "source"]):
                tag.decompose()
            for tag in soup(["header", "nav", "aside", "footer"]):
                tag.decompose()
            main_node = soup.find("article") or soup.find("main") or soup.body
            text = main_node.get_text(" ") if main_node else soup.get_text(" ")

    text = unescape(text)
    # Remove common cookie/consent strings if they slipped through
    text = re.sub(r"(?i)(we use cookies|cookie\s+settings|your\s+privacy|consent)", " ", text)
    # Remove CSS/JS artifacts
    text = re.sub(r"\{[^}]*\}", " ")  # CSS blocks
    text = re.sub(r";\s*}", " ")
    text = re.sub(r"\b(function|var|let|const|window\.|document\.)\b[\s\S]{0,120}", " ")
    # Remove markdown image syntax and data URIs
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ")
    text = re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", " ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ").strip()

    # Final safety fallback if still empty
    if not text:
        text = _basic_html_to_text(content)

    return text

