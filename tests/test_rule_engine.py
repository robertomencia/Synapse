"""Integration tests for the Rule Engine — no LLM, no network, no filesystem required.

These tests prove the core claim: a deterministic rule fires when three independent
context sources (dependency file, CVE feed, calendar) converge — something no linter,
hook, or single-source tool can detect.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from synapse.rules.state_store import (
    CalendarEvent,
    CVEEntry,
    DependencyInfo,
    StateStore,
)
from synapse.rules.rules import RULES, Rule, _cve_deploy_condition, _new_cve_condition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hours_from_now(hours: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _make_dep(name: str = "stripe", version: str = "4.2.1", ecosystem: str = "npm") -> DependencyInfo:
    return DependencyInfo(name=name, version=version, ecosystem=ecosystem, source_file="package.json")


def _make_cve(package: str = "stripe", severity: str = "high") -> CVEEntry:
    return CVEEntry(
        id="CVE-2024-38374",
        package=package,
        severity=severity,
        published=datetime.now(timezone.utc),
        description="Request forgery in webhook handling",
        feed_url="https://github.com/stripe/stripe-node/releases.atom",
    )


def _make_deploy_event(hours_from_now: float = 1.5) -> CalendarEvent:
    return CalendarEvent(
        uid="deploy-001",
        summary="Production Deploy",
        start=_hours_from_now(hours_from_now),
        tags=["deploy"],
    )


# ---------------------------------------------------------------------------
# StateStore unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_state_store_starts_empty() -> None:
    store = StateStore()
    state = await store.snapshot()
    assert state.dependencies == {}
    assert state.cve_entries == []
    assert state.upcoming_events == []


@pytest.mark.asyncio
async def test_state_store_update_and_snapshot() -> None:
    store = StateStore()

    dep = _make_dep()
    cve = _make_cve()
    event = _make_deploy_event()

    await store.update_dependencies({"stripe@4.2.1": dep})
    await store.update_cves([cve])
    await store.update_calendar([event])

    state = await store.snapshot()

    assert "stripe@4.2.1" in state.dependencies
    assert state.dependencies["stripe@4.2.1"].name == "stripe"
    assert len(state.cve_entries) == 1
    assert state.cve_entries[0].id == "CVE-2024-38374"
    assert len(state.upcoming_events) == 1
    assert "deploy" in state.upcoming_events[0].tags


@pytest.mark.asyncio
async def test_snapshot_is_a_copy() -> None:
    """Mutations to a snapshot don't affect the store."""
    store = StateStore()
    await store.update_dependencies({"stripe@4.2.1": _make_dep()})

    snap1 = await store.snapshot()
    snap1.dependencies.clear()

    snap2 = await store.snapshot()
    assert "stripe@4.2.1" in snap2.dependencies


# ---------------------------------------------------------------------------
# Rule condition unit tests — pure functions, no async needed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cve_deploy_rule_fires_when_all_three_sources_present() -> None:
    """THE core test: rule fires only when CVE + dependency + deploy all converge."""
    store = StateStore()
    await store.update_dependencies({"stripe@4.2.1": _make_dep()})
    await store.update_cves([_make_cve()])
    await store.update_calendar([_make_deploy_event(hours_from_now=1.5)])

    state = await store.snapshot()
    assert _cve_deploy_condition(state) is True


@pytest.mark.asyncio
async def test_cve_deploy_rule_does_not_fire_without_deploy() -> None:
    """CVE present, dependency present, but no deploy scheduled — rule must NOT fire."""
    store = StateStore()
    await store.update_dependencies({"stripe@4.2.1": _make_dep()})
    await store.update_cves([_make_cve()])
    # No calendar event

    state = await store.snapshot()
    assert _cve_deploy_condition(state) is False


@pytest.mark.asyncio
async def test_cve_deploy_rule_does_not_fire_without_matching_dependency() -> None:
    """CVE for 'stripe' but workspace uses 'lodash' — rule must NOT fire."""
    store = StateStore()
    await store.update_dependencies({"lodash@4.17.21": _make_dep(name="lodash", version="4.17.21")})
    await store.update_cves([_make_cve(package="stripe")])  # Different package
    await store.update_calendar([_make_deploy_event()])

    state = await store.snapshot()
    assert _cve_deploy_condition(state) is False


@pytest.mark.asyncio
async def test_cve_deploy_rule_does_not_fire_without_cve() -> None:
    """Dependency present, deploy scheduled, but no CVEs — should not fire."""
    store = StateStore()
    await store.update_dependencies({"stripe@4.2.1": _make_dep()})
    await store.update_calendar([_make_deploy_event()])
    # No CVEs

    state = await store.snapshot()
    assert _cve_deploy_condition(state) is False


@pytest.mark.asyncio
async def test_cve_deploy_rule_does_not_fire_for_old_deploy() -> None:
    """Deploy is 3 hours away (beyond 2h window) — rule must NOT fire."""
    store = StateStore()
    await store.update_dependencies({"stripe@4.2.1": _make_dep()})
    await store.update_cves([_make_cve()])
    await store.update_calendar([_make_deploy_event(hours_from_now=3.0)])

    state = await store.snapshot()
    assert _cve_deploy_condition(state) is False


@pytest.mark.asyncio
async def test_cve_deploy_rule_fires_for_deploy_at_limit() -> None:
    """Deploy exactly at 1:59 (just under 2h) — should fire."""
    store = StateStore()
    await store.update_dependencies({"stripe@4.2.1": _make_dep()})
    await store.update_cves([_make_cve()])
    await store.update_calendar([_make_deploy_event(hours_from_now=1.98)])

    state = await store.snapshot()
    assert _cve_deploy_condition(state) is True


@pytest.mark.asyncio
async def test_new_cve_rule_fires_without_deploy() -> None:
    """new_cve_in_active_dep fires whenever a CVE matches, deploy not required."""
    store = StateStore()
    await store.update_dependencies({"stripe@4.2.1": _make_dep()})
    await store.update_cves([_make_cve()])

    state = await store.snapshot()
    assert _new_cve_condition(state) is True


@pytest.mark.asyncio
async def test_new_cve_rule_does_not_fire_empty_workspace() -> None:
    store = StateStore()
    await store.update_cves([_make_cve()])
    # No dependencies scanned

    state = await store.snapshot()
    assert _new_cve_condition(state) is False


# ---------------------------------------------------------------------------
# Rule Engine integration — fire → event bus
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rule_engine_publishes_event_when_rule_fires() -> None:
    """End-to-end: engine evaluates rules, publishes rule.fired on bus."""
    from synapse.event_bus import EventBus, SynapseEvent
    from synapse.rules.engine import RuleEngine

    test_bus = EventBus()
    await test_bus.start()

    fired_events: list[SynapseEvent] = []

    async def capture(event: SynapseEvent) -> None:
        fired_events.append(event)

    test_bus.subscribe("rule.fired", capture)

    # Patch global bus used by RuleEngine
    import synapse.rules.engine as engine_module
    original_bus = engine_module.bus
    engine_module.bus = test_bus

    try:
        store = StateStore()
        await store.update_dependencies({"stripe@4.2.1": _make_dep()})
        await store.update_cves([_make_cve()])
        await store.update_calendar([_make_deploy_event(hours_from_now=1.0)])

        engine = RuleEngine(store, RULES, eval_interval=999)
        await engine._evaluate_all()

        # Give bus a tick to dispatch
        await asyncio.sleep(0.05)

        assert len(fired_events) >= 1
        rule_ids = [e.payload["rule_id"] for e in fired_events]
        assert "cve_before_deploy" in rule_ids

    finally:
        engine_module.bus = original_bus
        await test_bus.stop()


@pytest.mark.asyncio
async def test_rule_engine_respects_cooldown() -> None:
    """A rule that just fired must not fire again within cooldown window."""
    from synapse.event_bus import EventBus
    from synapse.rules.engine import RuleEngine

    test_bus = EventBus()
    await test_bus.start()

    fired_events = []

    async def capture(event) -> None:
        fired_events.append(event)

    test_bus.subscribe("rule.fired", capture)

    import synapse.rules.engine as engine_module
    original_bus = engine_module.bus
    engine_module.bus = test_bus

    try:
        store = StateStore()
        await store.update_dependencies({"stripe@4.2.1": _make_dep()})
        await store.update_cves([_make_cve()])
        await store.update_calendar([_make_deploy_event()])

        engine = RuleEngine(store, RULES, eval_interval=999)

        # First evaluation — should fire
        await engine._evaluate_all()
        await asyncio.sleep(0.05)
        first_count = len(fired_events)
        assert first_count >= 1

        # Second evaluation immediately after — cooldown active, must NOT fire again
        await engine._evaluate_all()
        await asyncio.sleep(0.05)
        assert len(fired_events) == first_count  # No new events

    finally:
        engine_module.bus = original_bus
        await test_bus.stop()


@pytest.mark.asyncio
async def test_rule_event_payload_structure() -> None:
    """rule.fired payload must contain all fields ProactiveAgent expects."""
    from synapse.event_bus import EventBus
    from synapse.rules.engine import RuleEngine

    test_bus = EventBus()
    await test_bus.start()

    fired_events = []

    async def capture(event) -> None:
        fired_events.append(event)

    test_bus.subscribe("rule.fired", capture)

    import synapse.rules.engine as engine_module
    original_bus = engine_module.bus
    engine_module.bus = test_bus

    try:
        store = StateStore()
        await store.update_dependencies({"stripe@4.2.1": _make_dep()})
        await store.update_cves([_make_cve()])
        await store.update_calendar([_make_deploy_event()])

        engine = RuleEngine(store, RULES, eval_interval=999)
        await engine._evaluate_all()
        await asyncio.sleep(0.05)

        assert fired_events
        payload = fired_events[0].payload

        # Fields that ProactiveAgent.process() reads
        assert "rule_id" in payload
        assert "rule_name" in payload
        assert "rule_description" in payload
        assert "action_id" in payload
        assert "priority" in payload
        assert "context" in payload

        ctx = payload["context"]
        assert "cves" in ctx
        assert "deploy_event" in ctx
        assert "minutes_to_deploy" in ctx
        assert "affected_packages" in ctx

        assert ctx["minutes_to_deploy"] > 0
        assert len(ctx["cves"]) == 1
        assert ctx["cves"][0]["id"] == "CVE-2024-38374"

    finally:
        engine_module.bus = original_bus
        await test_bus.stop()


# ---------------------------------------------------------------------------
# Dependency parser unit tests
# ---------------------------------------------------------------------------

def test_parse_package_json(tmp_path) -> None:
    import json
    from synapse.collectors.dependency_collector import DependencyCollector
    from synapse.rules.state_store import StateStore

    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({
        "dependencies": {
            "stripe": "^4.2.1",
            "express": "~4.18.0",
        },
        "devDependencies": {
            "jest": "^29.0.0",
        }
    }))

    store = StateStore()
    collector = DependencyCollector(store)
    deps = collector._parse_package_json(pkg)

    assert "stripe@4.2.1" in deps
    assert deps["stripe@4.2.1"].ecosystem == "npm"
    assert deps["stripe@4.2.1"].version == "4.2.1"  # ^ stripped
    assert "express@4.18.0" in deps
    assert "jest@29.0.0" in deps


def test_parse_requirements_txt(tmp_path) -> None:
    from synapse.collectors.dependency_collector import DependencyCollector
    from synapse.rules.state_store import StateStore

    req = tmp_path / "requirements.txt"
    req.write_text(
        "django==4.2.1\n"
        "requests>=2.31.0\n"
        "cryptography~=41.0\n"
        "# this is a comment\n"
        "\n"
        "pillow\n"
    )

    store = StateStore()
    collector = DependencyCollector(store)
    deps = collector._parse_requirements_txt(req)

    assert "django@4.2.1" in deps
    assert deps["django@4.2.1"].ecosystem == "pip"
    assert "requests@2.31.0" in deps
    assert "cryptography@41.0" in deps
    assert "pillow@latest" in deps


# ---------------------------------------------------------------------------
# RSS feed parser unit tests
# ---------------------------------------------------------------------------

def test_rss_parser_extracts_cve_from_atom_xml() -> None:
    from synapse.collectors.rss_collector import _parse_atom_feed

    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Release 4.2.2 — Security fix: CVE-2024-38374 request forgery in webhook handling (high severity)</title>
    <content>This release fixes a high severity vulnerability CVE-2024-38374.</content>
    <updated>2024-06-15T10:00:00Z</updated>
  </entry>
  <entry>
    <title>Release 4.2.0 — Add new payment methods</title>
    <content>Added support for SEPA direct debit.</content>
    <updated>2024-05-01T10:00:00Z</updated>
  </entry>
</feed>"""

    entries = _parse_atom_feed(xml, "https://github.com/stripe/stripe-node/releases.atom", "stripe")

    assert len(entries) == 1
    assert entries[0].id == "CVE-2024-38374"
    assert entries[0].package == "stripe"
    assert entries[0].severity == "high"


def test_rss_parser_returns_empty_for_no_cve() -> None:
    from synapse.collectors.rss_collector import _parse_atom_feed

    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Release 5.0.0 — New async API</title>
    <content>Major API redesign.</content>
    <updated>2024-07-01T10:00:00Z</updated>
  </entry>
</feed>"""

    entries = _parse_atom_feed(xml, "https://example.com/releases.atom", "stripe")
    assert entries == []


def test_rss_parser_deduplicates_cve_ids() -> None:
    from synapse.collectors.rss_collector import _parse_atom_feed

    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>CVE-2024-1111 and CVE-2024-1111 duplicate mention</title>
    <content>Two mentions of CVE-2024-1111 in same entry.</content>
    <updated>2024-06-01T10:00:00Z</updated>
  </entry>
</feed>"""

    entries = _parse_atom_feed(xml, "https://example.com", "somelib")
    cve_ids = [e.id for e in entries]
    assert cve_ids.count("CVE-2024-1111") == 1


# ---------------------------------------------------------------------------
# Calendar event tagging
# ---------------------------------------------------------------------------

def test_calendar_tags_deploy_events() -> None:
    from synapse.collectors.calendar_collector import _tag_event

    assert "deploy" in _tag_event("Production Deploy")
    assert "deploy" in _tag_event("Release v2.0 rollout")
    assert "deploy" in _tag_event("Go live — new checkout flow")
    assert "meeting" in _tag_event("Engineering Sync")
    assert "deadline" in _tag_event("Q2 milestone submission due")
    assert _tag_event("Team lunch") == []


def test_calendar_event_not_tagged_as_deploy_for_meetings() -> None:
    from synapse.collectors.calendar_collector import _tag_event

    tags = _tag_event("Weekly standup with product")
    assert "deploy" not in tags
    assert "meeting" in tags
