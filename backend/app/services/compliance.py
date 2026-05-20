"""
Compliance gate — runs before any outbound call is placed.

Two independent checks, both required by the Australian regime described in
PROJECT_PLAN.md section 6:

  1. Do Not Call — the customer's `do_not_call` flag is honoured regardless
     of the Existing Customer Relationship exemption. This check can NEVER
     be bypassed.
  2. Calling hours — the Telemarketing Industry Standard 2017 restricts when
     telemarketing calls may be made. Evaluated against a single configured
     timezone (see config.calling_timezone). Can be bypassed for demos via
     config.calling_hours_override — the DNC check cannot.

`check_customer` is the single entry point. It returns a structured result
the call service and the API layer can act on, rather than raising — the
dashboard wants to show *why* a call was blocked, not just that it was.

This is design-level compliance scaffolding, not legal advice. Public
holidays are out of scope for the demo (noted in PROJECT_PLAN open items).

Kept HTTP-free so it can be unit-tested directly.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings

logger = logging.getLogger(__name__)

# Bad timezone names we've already warned about, so the log isn't spammed
# once per call. Bounded by the (tiny) set of misconfigured values seen.
_warned_bad_timezones: set[str] = set()

# Reasons a call is blocked — stable string codes the frontend can switch on.
REASON_DO_NOT_CALL = "do_not_call"
REASON_OUTSIDE_HOURS = "outside_calling_hours"
REASON_NO_CONSENT = "no_consent"


@dataclass
class ComplianceResult:
    """Outcome of the pre-dial compliance gate."""

    allowed: bool
    reason: str | None = None  # one of the REASON_* codes when blocked
    message: str = ""  # human-readable explanation for the UI
    checked_at: str = ""  # ISO timestamp the gate ran
    timezone: str = ""  # timezone the hours check used

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "message": self.message,
            "checked_at": self.checked_at,
            "timezone": self.timezone,
        }


def _local_now() -> datetime:
    """Current time in the configured calling timezone.

    Falls back to UTC if the timezone name is invalid rather than crashing —
    a misconfigured tz should not take the whole dialer down. Logs a warning
    the first time each bad value is seen so the misconfiguration is visible
    in operator logs (a silent fallback can shift the calling-hours gate by
    10+ hours and pass/fail calls at the wrong times all day).
    """
    bad_tz_name = settings.calling_timezone
    try:
        tz = ZoneInfo(bad_tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        if bad_tz_name not in _warned_bad_timezones:
            _warned_bad_timezones.add(bad_tz_name)
            logger.warning(
                "CALLING_TIMEZONE=%r is not a valid IANA timezone; "
                "falling back to UTC. The calling-hours gate will evaluate "
                "against UTC until this is fixed.",
                bad_tz_name,
            )
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def within_calling_hours(now: datetime | None = None) -> tuple[bool, str]:
    """Is `now` inside the permitted telemarketing window?

    Args:
        now: the local time to test. Defaults to the current time in the
            configured calling timezone — pass an explicit value in tests.

    Returns:
        (allowed, explanation). The explanation is suitable for showing in
        the dashboard whether or not the call is allowed.
    """
    now = now or _local_now()
    weekday = now.weekday()  # Mon=0 .. Sun=6
    hour = now.hour

    # Sunday — disallowed by default.
    if weekday == 6 and not settings.calling_allow_sunday:
        return (False, "Calls are not permitted on Sundays.")

    # Saturday — shorter window.
    if weekday == 5:
        end = settings.calling_hour_end_saturday
        label = "Saturday"
    else:
        end = settings.calling_hour_end_weekday
        label = "weekday"

    start = settings.calling_hour_start
    if start <= hour < end:
        return (
            True,
            f"Within {label} calling hours "
            f"({start:02d}:00–{end:02d}:00 {settings.calling_timezone}).",
        )
    return (
        False,
        f"Outside {label} calling hours — calls allowed "
        f"{start:02d}:00–{end:02d}:00 {settings.calling_timezone}, "
        f"now {now:%H:%M}.",
    )


def check_customer(customer: dict, now: datetime | None = None) -> ComplianceResult:
    """Run the full pre-dial compliance gate for one customer.

    Args:
        customer: the customer document (must include `do_not_call`; may
            include `consent`).
        now: optional local time override for the calling-hours check.

    Returns:
        A ComplianceResult. `allowed` is True only if every check passes.

    Order matters: do_not_call is checked first and is absolute. Calling
    hours are checked second and may be bypassed via config for demos.
    """
    checked_at = _local_now().isoformat()
    base = {"checked_at": checked_at, "timezone": settings.calling_timezone}

    # --- 1. Do Not Call — absolute, never bypassed ---
    if customer.get("do_not_call", False):
        return ComplianceResult(
            allowed=False,
            reason=REASON_DO_NOT_CALL,
            message="Customer is flagged do-not-call and must not be dialled.",
            **base,
        )

    # --- 1b. Consent — an existing customer should have a consent record.
    # Treat an explicitly withdrawn consent record as a block: the Existing
    # Customer Relationship exemption rests on that relationship existing.
    consent = customer.get("consent") or {}
    if consent and consent.get("given") is False:
        return ComplianceResult(
            allowed=False,
            reason=REASON_NO_CONSENT,
            message="Customer has no current consent on record.",
            **base,
        )

    # --- 2. Calling hours — bypassable for demos ---
    if not settings.calling_hours_override:
        ok, why = within_calling_hours(now)
        if not ok:
            return ComplianceResult(
                allowed=False,
                reason=REASON_OUTSIDE_HOURS,
                message=why,
                **base,
            )
        hours_note = why
    else:
        hours_note = "Calling-hours gate is overridden (demo mode)."

    return ComplianceResult(
        allowed=True,
        reason=None,
        message=f"Cleared to call. {hours_note}",
        **base,
    )
