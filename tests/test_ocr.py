"""Tests for any2txt.ocr.rapid_ocr."""

from numpy import array

from any2txt.ocr.rapid_ocr import _sort_and_join


def test_sort_and_join_orders_by_top_edge() -> None:
    """Texts are ordered top-to-bottom by their box top edges."""
    boxes = array([[[0, 100], [10, 100], [10, 120], [0, 120]], [[0, 0], [10, 0], [10, 20], [0, 20]]])
    assert _sort_and_join(('bottom', 'top'), boxes) == 'top\nbottom'


def test_sort_and_join_no_text() -> None:
    """None or empty texts produce an empty string."""
    assert _sort_and_join(None, None) == ''
    assert _sort_and_join((), array([])) == ''


def test_sort_and_join_without_boxes_keeps_order() -> None:
    """Missing boxes keep the detection order."""
    assert _sort_and_join(('a', 'b'), None) == 'a\nb'


def test_sort_and_join_misaligned_boxes_keeps_order() -> None:
    """A box/text count mismatch keeps the detection order."""
    boxes = array([[[0, 0], [10, 0], [10, 20], [0, 20]]])
    assert _sort_and_join(('a', 'b'), boxes) == 'a\nb'
