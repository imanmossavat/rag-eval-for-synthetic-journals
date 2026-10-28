"""Piece 4 (Bundle 21, item A6 / N12): validate_corpus warns when the corpus's
realized calendar span is far from the configured DURATION_DAYS, so the mismatch
(measured 21 days vs a configured 90) stops being silent."""
import validate_corpus as vc


def _notes(*iso_timestamps):
    return [{"timestamp": t} for t in iso_timestamps]


def test_span_days_needs_two_timestamps():
    assert vc._span_days([]) is None
    assert vc._span_days(_notes("2024-01-01T00:00:00")) is None


def test_span_days_measures_range():
    span = vc._span_days(_notes("2024-01-01T00:00:00", "2024-01-22T00:00:00"))
    assert abs(span - 21.0) < 1e-6


def test_warns_when_span_far_from_configured():
    notes = _notes("2024-01-01T00:00:00", "2024-01-22T00:00:00")  # 21 days
    assert vc._span_warning(notes, configured_days=90) is not None


def test_silent_when_span_within_tolerance():
    notes = _notes("2024-01-01T00:00:00", "2024-03-31T00:00:00")  # ~90 days
    assert vc._span_warning(notes, configured_days=90) is None


def test_silent_when_too_few_timestamps():
    assert vc._span_warning(_notes("2024-01-01T00:00:00"), configured_days=90) is None
