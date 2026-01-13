"""Tests for any2txt.formats.srt."""

from any2txt.asr import Segment
from any2txt.formats.srt import display_width, format_srt, format_srt_time, wrap_text


def test_format_srt_time_milliseconds() -> None:
    """Seconds are converted to hh:mm:ss,mmm with a comma separator."""
    assert format_srt_time(0.0) == '00:00:00,000'
    assert format_srt_time(3661.25) == '01:01:01,250'
    assert format_srt_time(2.9996) == '00:00:03,000'


def test_format_srt_entries() -> None:
    """Segments are numbered sequentially with start --> end timelines."""
    segments = [
        Segment(start=0.0, end=2.0, text='Hello.'),
        Segment(start=61.0, end=63.0, text='World.'),
    ]
    expected = '1\n00:00:00,000 --> 00:00:02,000\nHello.\n\n2\n00:01:01,000 --> 00:01:03,000\nWorld.'
    assert format_srt(segments) == expected


def test_format_srt_skips_empty_segments_without_number_gap() -> None:
    """Empty segments are dropped and do not consume a sequence number."""
    segments = [
        Segment(start=0.0, end=2.0, text='   '),
        Segment(start=12.0, end=15.0, text='Kept.'),
    ]
    expected = '1\n00:00:12,000 --> 00:00:15,000\nKept.'
    assert format_srt(segments) == expected


def test_format_srt_empty_input() -> None:
    """No segments yields an empty string."""
    assert format_srt([]) == ''


def test_display_width_counts_fullwidth_as_two() -> None:
    """Full-width characters count as 2, half-width as 1."""
    assert display_width('abc') == 3
    assert display_width('中文') == 4
    assert display_width('中a，') == 5
    assert display_width('') == 0


def test_wrap_text_short_text_unchanged() -> None:
    """Text within the budget stays on a single line."""
    assert wrap_text('Hello world.', 42) == 'Hello world.'


def test_wrap_text_breaks_chinese_at_width() -> None:
    """Full-width text breaks so lines stay within the width budget."""
    text = '一二三四五六七八九十' * 4  # 40 chars = width 80
    wrapped = wrap_text(text, 42)
    lines = wrapped.split('\n')
    assert len(lines) == 2
    assert display_width(lines[0]) <= 42
    assert wrapped.replace('\n', '') == text


def test_wrap_text_never_splits_halfwidth_words() -> None:
    """Half-width words are kept intact and break at spaces."""
    text = 'alpha beta gamma delta epsilon'
    wrapped = wrap_text(text, 10)
    lines = wrapped.split('\n')
    assert lines[0] == 'alpha beta'
    assert lines[1] == 'gamma'
    assert lines[2] == 'delta'
    assert lines[3] == 'epsilon'


def test_wrap_text_avoids_leading_punctuation() -> None:
    """A closing punctuation is pulled up instead of starting a line."""
    # 10 Chinese chars fill the width budget of 10; the comma would wrap.
    text = '一二三四五' + '，' + '六七八九十'
    wrapped = wrap_text(text, 10)
    lines = wrapped.split('\n')
    assert lines[0] == '一二三四五，'
    assert not lines[1].startswith('，')


def test_wrap_text_mixed_width_budget() -> None:
    """Mixed CJK and Latin text respects the display width budget."""
    text = '中文字符 alpha 中文字符 beta'
    wrapped = wrap_text(text, 12)
    for line in wrapped.split('\n'):
        assert display_width(line) <= 12


def test_wrap_text_collapses_consecutive_spaces() -> None:
    """Runs of spaces never produce multiple consecutive spaces in output."""
    wrapped = wrap_text('alpha    beta', 42)
    assert wrapped == 'alpha beta'
    assert '  ' not in wrapped


def test_format_srt_zero_duration_segment_is_not_split() -> None:
    """Zero-duration segments stay a single cue even when text is long."""
    text = '一二三四五六七八九十' * 6  # wraps to 3 lines
    segments = [Segment(start=5.0, end=5.0, text=text)]
    result = format_srt(segments, line_width=42)
    entries = result.split('\n\n')
    assert len(entries) == 1
    assert '00:00:05,000 --> 00:00:05,000' in entries[0]
    assert len(entries[0].split('\n')) == 1 + 1 + 3  # index, timeline, 3 lines


def test_format_srt_wraps_long_segments() -> None:
    """A segment wrapping to two lines stays a single two-line cue."""
    segments = [Segment(start=0.0, end=5.0, text='一二三四五六七八九十' * 4)]
    result = format_srt(segments, line_width=42)
    body = result.split('\n', 2)[2]
    assert len(body.split('\n')) == 2


def test_format_srt_splits_long_segment_into_cues() -> None:
    """A segment wrapping beyond max_lines is split into several cues."""
    text = '一二三四五六七八九十' * 6  # 60 chars -> lines of 21/21/18 chars
    segments = [Segment(start=0.0, end=10.0, text=text)]
    result = format_srt(segments, line_width=42)
    assert result == (
        f'1\n00:00:00,000 --> 00:00:07,000\n{text[:21]}\n{text[21:42]}\n\n2\n00:00:07,000 --> 00:00:10,000\n{text[42:]}'
    )


def test_format_srt_cue_times_are_contiguous() -> None:
    """Split cues start where the previous one ends and cover the segment."""
    text = '一二三四五六七八九十' * 6
    segments = [Segment(start=3.0, end=13.0, text=text)]
    result = format_srt(segments, line_width=42)
    entries = result.split('\n\n')
    assert '00:00:03,000 --> 00:00:10,000' in entries[0]
    assert '00:00:10,000 --> 00:00:13,000' in entries[1]


def test_format_srt_max_lines_one_splits_every_line() -> None:
    """max_lines=1 turns every wrapped line into its own cue."""
    segments = [Segment(start=0.0, end=2.0, text='一二三四五' * 2)]  # 10 chars -> 2 lines at width 10
    result = format_srt(segments, line_width=10, max_lines=1)
    entries = result.split('\n\n')
    assert len(entries) == 2
    assert '00:00:00,000 --> 00:00:01,000' in entries[0]
    assert '00:00:01,000 --> 00:00:02,000' in entries[1]
