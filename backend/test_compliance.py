"""Test the compliance gate's timezone handling.

A typo'd CALLING_TIMEZONE (e.g. Asia/Sidney) used to silently fall back to
UTC, which is 10–11 hours off Australia/Sydney. The gate would then pass or
fail calls at the wrong times all day. The fix keeps the fallback (so the
dialer stays up) but surfaces a non-fatal warning so operators see it.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.services import compliance


def run():
    # --- 1. bad timezone falls back to UTC and emits a warning ----------------
    original_tz = settings.calling_timezone
    compliance._warned_bad_timezones.clear()

    settings.calling_timezone = "Asia/Sidney"  # typo for Australia/Sydney
    try:
        with _capture_logs(compliance.logger) as records:
            now = compliance._local_now()

        assert now.utcoffset().total_seconds() == 0, \
            f"bad tz must fall back to UTC, got offset {now.utcoffset()}"

        warnings = [r for r in records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, \
            f"expected one WARNING about bad tz, got {len(warnings)}"
        assert "Asia/Sidney" in warnings[0].getMessage()
        assert "UTC" in warnings[0].getMessage()
        print("  bad tz          -> falls back to UTC, warns once")

        # --- 2. same bad tz on repeat calls does not re-spam the log ---------
        with _capture_logs(compliance.logger) as records2:
            for _ in range(5):
                compliance._local_now()
        warnings2 = [r for r in records2 if r.levelno == logging.WARNING]
        assert warnings2 == [], \
            f"repeat calls with same bad tz must not re-warn, got {len(warnings2)}"
        print("  repeat bad tz   -> no duplicate warnings")

        # --- 3. gate behavior is unchanged from explicit UTC -----------------
        # Pick a time inside both windows: Tue 10:00 UTC.
        sample = datetime(2026, 5, 19, 10, 0, tzinfo=ZoneInfo("UTC"))
        ok_bad, _ = compliance.within_calling_hours(sample)

        settings.calling_timezone = "UTC"
        ok_utc, _ = compliance.within_calling_hours(sample)
        assert ok_bad == ok_utc, \
            "bad-tz behavior must match explicit UTC for the same wall time"
        print("  gate behavior   -> bad tz matches UTC")
    finally:
        settings.calling_timezone = original_tz
        compliance._warned_bad_timezones.clear()

    # --- 4. a valid tz must NOT warn -----------------------------------------
    settings.calling_timezone = "Australia/Sydney"
    try:
        with _capture_logs(compliance.logger) as records:
            compliance._local_now()
        warnings = [r for r in records if r.levelno == logging.WARNING]
        assert warnings == [], \
            f"valid tz must not produce warnings, got {[w.getMessage() for w in warnings]}"
        print("  valid tz        -> no warning")
    finally:
        settings.calling_timezone = original_tz


class _capture_logs:
    """Capture records emitted to a logger for the duration of the block."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._handler = _ListHandler()

    def __enter__(self):
        self._prev_level = self._logger.level
        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(self._handler)
        return self._handler.records

    def __exit__(self, *exc):
        self._logger.removeHandler(self._handler)
        self._logger.setLevel(self._prev_level)


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


run()
print("\nALL COMPLIANCE CHECKS PASSED")
