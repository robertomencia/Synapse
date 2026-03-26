"""RSS/Atom feed collector — polls GitHub release feeds for CVEs."""

from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from synapse.collectors.base import BaseCollector
from synapse.rules.state_store import CVEEntry

if TYPE_CHECKING:
    from synapse.rules.state_store import StateStore

logger = logging.getLogger(__name__)

_CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_SEVERITY_KEYWORDS = {
    "critical": "critical",
    "rce": "critical",
    "remote code execution": "critical",
    "high": "high",
    "medium": "medium",
    "moderate": "medium",
    "low": "low",
}

# GitHub npm package → repo mapping for common packages
_NPM_TO_GITHUB: dict[str, str] = {
    "stripe": "stripe/stripe-node",
    "axios": "axios/axios",
    "express": "expressjs/express",
    "lodash": "lodash/lodash",
    "moment": "moment/moment",
    "jsonwebtoken": "auth0/node-jsonwebtoken",
    "bcrypt": "kelektiv/node.bcrypt.js",
    "dotenv": "motdotla/dotenv",
    "mongoose": "Automattic/mongoose",
    "sequelize": "sequelize/sequelize",
    "next": "vercel/next.js",
    "react": "facebook/react",
    "vue": "vuejs/vue",
    "angular": "angular/angular",
}

# PyPI package → GitHub repo mapping
_PIP_TO_GITHUB: dict[str, str] = {
    "django": "django/django",
    "flask": "pallets/flask",
    "fastapi": "tiangolo/fastapi",
    "requests": "psf/requests",
    "cryptography": "pyca/cryptography",
    "pillow": "python-pillow/Pillow",
    "sqlalchemy": "sqlalchemy/sqlalchemy",
    "pydantic": "pydantic/pydantic",
    "celery": "celery/celery",
    "paramiko": "paramiko/paramiko",
}

ATOM_NS = "http://www.w3.org/2005/Atom"


def _detect_severity(text: str) -> str:
    lower = text.lower()
    for keyword, severity in _SEVERITY_KEYWORDS.items():
        if keyword in lower:
            return severity
    return "unknown"


def _parse_atom_feed(xml_text: str, feed_url: str, package_name: str) -> list[CVEEntry]:
    """Parse a GitHub Atom releases feed and extract CVE entries."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("Failed to parse Atom feed from %s: %s", feed_url, e)
        return []

    entries = []
    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        title_el = entry.find(f"{{{ATOM_NS}}}title")
        content_el = entry.find(f"{{{ATOM_NS}}}content")
        updated_el = entry.find(f"{{{ATOM_NS}}}updated")

        title = title_el.text or "" if title_el is not None else ""
        content = content_el.text or "" if content_el is not None else ""
        full_text = f"{title} {content}"

        cve_ids = _CVE_PATTERN.findall(full_text)
        if not cve_ids:
            continue

        published = datetime.now(timezone.utc)
        if updated_el is not None and updated_el.text:
            try:
                published = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
            except ValueError:
                pass

        severity = _detect_severity(full_text)

        for cve_id in set(cve_ids):
            entries.append(CVEEntry(
                id=cve_id.upper(),
                package=package_name,
                severity=severity,
                published=published,
                description=title[:200],
                feed_url=feed_url,
            ))

    return entries


class RSSCollector(BaseCollector):
    """Polls GitHub release Atom feeds for CVEs matching current dependencies."""

    def __init__(
        self,
        state_store: "StateStore",
        extra_feed_urls: list[str] | None = None,
        poll_interval: int = 300,
    ) -> None:
        super().__init__(state_store)
        self._extra_urls = extra_feed_urls or []
        self._poll_interval = poll_interval
        self._running = False
        self._session = None

    async def start(self) -> None:
        import aiohttp
        self._running = True
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Synapse/1.0 (security monitoring)"},
        )
        logger.info("RSSCollector started (poll every %ds)", self._poll_interval)
        while self._running:
            await self._poll_all()
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._session:
            await self._session.close()

    async def _poll_all(self) -> None:
        state = await self._store.snapshot()
        feed_urls = self._build_feed_urls(state.dependencies)
        feed_urls.extend(self._extra_urls)

        if not feed_urls:
            return

        all_cves: list[CVEEntry] = []
        tasks = [self._fetch_feed(url, pkg) for url, pkg in feed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.debug("Feed fetch error: %s", result)
            elif result:
                all_cves.extend(result)

        if all_cves:
            # Deduplicate by CVE ID
            seen: dict[str, CVEEntry] = {}
            for cve in all_cves:
                if cve.id not in seen:
                    seen[cve.id] = cve
            unique_cves = list(seen.values())
            await self._store.update_cves(unique_cves)
            logger.info("RSSCollector: found %d CVE(s): %s",
                        len(unique_cves), [c.id for c in unique_cves])
        else:
            # Keep existing CVEs, just update timestamp via empty list only if we had deps
            if state.dependencies:
                logger.debug("RSSCollector: no CVEs found in %d feeds", len(feed_urls))

    def _build_feed_urls(self, dependencies: dict) -> list[tuple[str, str]]:
        """Build (feed_url, package_name) pairs from known dependencies."""
        pairs = []
        for dep_info in dependencies.values():
            name = dep_info.name.lower()
            repo = None
            if dep_info.ecosystem == "npm":
                repo = _NPM_TO_GITHUB.get(name)
            elif dep_info.ecosystem == "pip":
                repo = _PIP_TO_GITHUB.get(name)

            if repo:
                url = f"https://github.com/{repo}/releases.atom"
                pairs.append((url, dep_info.name))

        return pairs

    async def _fetch_feed(self, url: str, package_name: str) -> list[CVEEntry]:
        if not self._session:
            return []
        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return _parse_atom_feed(text, url, package_name)
                else:
                    logger.debug("Feed %s returned HTTP %d", url, resp.status)
        except Exception as e:
            logger.debug("Failed to fetch %s: %s", url, e)
        return []
