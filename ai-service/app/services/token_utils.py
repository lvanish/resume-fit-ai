"""Token counting for the typed-decisions tokenizer.

Counts use the same encoding Laya uses for state text: the checkpoint tokenizer
with special tokens disabled. Callers pass that tokenizer in. This module does
not estimate length from characters.
"""

from __future__ import annotations


def encode_ids(tokenizer, text: str) -> list[int]:
    """Token ids for `text`, matching `laya.common.encode_text` when possible."""
    if text == "":
        return []
    try:
        from laya.common import encode_text

        encoded = encode_text(tokenizer, text, add_special_tokens=False)
        return list(encoded["input_ids"])
    except TypeError:
        return list(tokenizer.encode(text, add_special_tokens=False))


def count_tokens(text: str, tokenizer) -> int:
    return len(encode_ids(tokenizer, text))


def truncate_to_tokens(text: str, max_tokens: int, tokenizer) -> str:
    """Return an extractive prefix of `text` whose token count is at most `max_tokens`.

    The cut is a character boundary of the original string. Decoding token ids
    is avoided so the retained text is not rewritten.
    """
    if max_tokens < 0:
        raise ValueError("max_tokens must be >= 0")
    if max_tokens == 0 or text == "":
        return ""
    if count_tokens(text, tokenizer) <= max_tokens:
        return text

    low = 0
    high = len(text)
    best = ""
    while low <= high:
        mid = (low + high) // 2
        piece = text[:mid]
        if count_tokens(piece, tokenizer) <= max_tokens:
            best = piece
            low = mid + 1
        else:
            high = mid - 1
    return best.rstrip()


def truncate_suffix_to_tokens(text: str, max_tokens: int, tokenizer) -> str:
    """Return an extractive suffix of `text` within `max_tokens`."""
    if max_tokens < 0:
        raise ValueError("max_tokens must be >= 0")
    if max_tokens == 0 or text == "":
        return ""
    if count_tokens(text, tokenizer) <= max_tokens:
        return text

    low = 0
    high = len(text)
    best = ""
    while low <= high:
        mid = (low + high) // 2
        piece = text[-mid:] if mid else ""
        if count_tokens(piece, tokenizer) <= max_tokens:
            best = piece
            low = mid + 1
        else:
            high = mid - 1
    return best.lstrip()
