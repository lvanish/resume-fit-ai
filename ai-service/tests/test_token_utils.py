import pytest

from app.services.token_utils import count_tokens, truncate_suffix_to_tokens, truncate_to_tokens


class CharTokenizer:
    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(character) for character in text]}


def test_count_tokens_uses_tokenizer_ids():
    assert count_tokens("abcd", CharTokenizer()) == 4
    assert count_tokens("", CharTokenizer()) == 0


def test_truncate_to_tokens_keeps_an_extractive_prefix():
    text = "abcdefghijklmnopqrstuvwxyz"
    truncated = truncate_to_tokens(text, 5, CharTokenizer())
    assert truncated == "abcde"
    assert count_tokens(truncated, CharTokenizer()) == 5
    assert truncate_to_tokens(text, 100, CharTokenizer()) == text


def test_truncate_suffix_keeps_the_end():
    text = "abcdefghijklmnopqrstuvwxyz"
    assert truncate_suffix_to_tokens(text, 4, CharTokenizer()) == "wxyz"


def test_truncate_rejects_a_negative_budget():
    with pytest.raises(ValueError):
        truncate_to_tokens("abc", -1, CharTokenizer())
