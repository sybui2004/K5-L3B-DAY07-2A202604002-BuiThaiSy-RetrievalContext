"""Simple Vietnamese tokenizers: whitespace syllables, and syllables + adjacent-pair bigrams."""
import re
import unicodedata


def tokenize_whitespace(text: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())


def tokenize_syllable_bigrams(text: str) -> list[str]:
    s = tokenize_whitespace(text)
    return s + [f"{a} {b}" for a, b in zip(s, s[1:])]
