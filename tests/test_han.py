"""Tests for any2txt.text.han."""

import pytest

from any2txt.text.han import HanVariant, convert_han


def test_convert_to_simplified() -> None:
    """Traditional characters are converted to simplified."""
    assert convert_han('簡體中文與繁體中文', HanVariant.SIMPLIFIED) == '简体中文与繁体中文'


def test_convert_to_traditional() -> None:
    """Simplified characters are converted to traditional."""
    assert convert_han('简体中文与繁体中文', HanVariant.TRADITIONAL) == '簡體中文與繁體中文'


def test_convert_auto_is_noop() -> None:
    """AUTO leaves the text unchanged."""
    text = '簡體中文'
    assert convert_han(text, HanVariant.AUTO) == text


def test_convert_han_variant_from_cli_string() -> None:
    """StrEnum values compare equal to their CLI strings."""
    assert HanVariant('simplified') is HanVariant.SIMPLIFIED


@pytest.mark.parametrize(
    ('variant', 'expected'),
    [
        (HanVariant.SIMPLIFIED, '简体中文'),
        (HanVariant.TRADITIONAL, '簡體中文'),
        (HanVariant.AUTO, '簡體中文'),
    ],
)
def test_convert_round_trip(variant: HanVariant, expected: str) -> None:
    """The simplified form converts back and forth consistently."""
    assert convert_han(convert_han('简体中文', HanVariant.TRADITIONAL), variant) == expected
