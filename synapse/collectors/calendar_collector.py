"""Calendar collector — reads local .ics files for upcoming events."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from synapse.collectors.base import BaseCollector
from synapse.rules.state_store import CalendarEvent

if TYPE_CHECKING:
    from synapse.rules.state_store import StateStore

logger = logging.getLogger(__name__)

# Keywords that tag events as deploys
_DEPLOY_KEYWORDS = re.compile(
    r"\b(deploy|deployment|release|rollout|ship|go.?live|production|prod)\b",
    re.IGNORECASE,
)
_MEETING_KEYWORDS = re.compile(
    r"\b(meeting|standup|stand.?up|sync|call|interview|review|retro)\b",
    re.IGNORECASE,
)
_DEADLINE_KEYWORDS = re.compile(
    r"\b(deadline|due|submit|delivery|milestone)\b",
    re.IGNORECASE,
)


def _tag_event(summary: str) -> list[str]:
    tags = []
    if _DEPLOY_KEYWORDS.search(summary):
        tags.append("deploy")
    if _MEETING_KEYWORDS.search(summary):
        tags.append("meeting")
    if _DEADLINE_KEYWORDS.search(summary):
        tags.append("deadline")
    return tags


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class CalendarCollector(BaseCollector):
    """Reads a local .ics file and surfaces upcoming events to the StateStore."""

    def __init__(
        self,
        state_store: "StateStore",
        ics_path: Path,
        poll_interval: int = 60,
        lookahead_hours: int = 4,
    ) -> None:
        super().__init__(state_store)
        self._ics_path = ics_path
        self._poll_interval = poll_interval
        self._lookahead = timedelta(hours=lookahead_hours)
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("CalendarCollector started, watching %s", self._ics_path)
        while self._running:
            await self._read_calendar()
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        self._running = False

    async def _read_calendar(self) -> None:
        try:
            from icalendar import Calendar  # type: ignore[import]
        except ImportError:
            logger.warning("icalendar package not installed. Run: pip install icalendar")
            self._running = False
            return

        if not self._ics_path.exists():
            logger.debug("Calendar file not found: %s", self._ics_path)
            return

        try:
            raw = self._ics_path.read_bytes()
            cal = Calendar.from_ical(raw)
        except Exception as e:
            logger.warning("Failed to parse calendar %s: %s", self._ics_path, e)
            return

        now = datetime.now(timezone.utc)
        horizon = now + self._lookahead
        upcoming: list[CalendarEvent] = []

        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            dtstart = component.get("DTSTART")
            if dtstart is None:
                continue

            start_dt = dtstart.dt
            # Handle date-only events (no time component)
            if not isinstance(start_dt, datetime):
                start_dt = datetime.combine(start_dt, datetime.min.time(), tzinfo=timezone.utc)
            else:
                start_dt = _to_utc(start_dt)

            if not (now <= start_dt <= horizon):
                continue

            summary = str(component.get("SUMMARY", ""))
            uid = str(component.get("UID", f"event-{start_dt.isoformat()}"))

            dtend = component.get("DTEND")
            end_dt = None
            if dtend is not None:
                end_dt_raw = dtend.dt
                if not isinstance(end_dt_raw, datetime):
                    end_dt_raw = datetime.combine(end_dt_raw, datetime.min.time(), tzinfo=timezone.utc)
                else:
                    end_dt_raw = _to_utc(end_dt_raw)
                end_dt = end_dt_raw

            tags = _tag_event(summary)

            upcoming.append(CalendarEvent(
                uid=uid,
                summary=summary,
                start=start_dt,
                end=end_dt,
                tags=tags,
            ))

        await self._store.update_calendar(upcoming)
        if upcoming:
            logger.info(
                "CalendarCollector: %d upcoming event(s) in next %dh: %s",
                len(upcoming),
                int(self._lookahead.total_seconds() / 3600),
                [e.summary for e in upcoming],
            )
