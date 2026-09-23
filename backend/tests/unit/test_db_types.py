from datetime import UTC, datetime

import pytest

from app.db.types import UTCDateTime


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValueError):
        UTCDateTime().process_bind_param(datetime(2026, 1, 1), None)


def test_values_come_back_as_utc_aware() -> None:
    value = UTCDateTime().process_result_value(datetime(2026, 1, 1, 12, 0), None)
    assert value.tzinfo is UTC
