import re


_WHITESPACE_RE = re.compile(r"[ \t]+")
_BROKEN_HYPHEN_RE = re.compile(r"(\w)-\n(\w)")
_SOFT_LINEBREAK_RE = re.compile(r"(?<![.!?:;])\n(?!\n)")


def clean_page_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = _BROKEN_HYPHEN_RE.sub(r"\1\2", text)
    text = _SOFT_LINEBREAK_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    # A conservative approximation for English-heavy academic text.
    return max(1, len(text) // 4)

