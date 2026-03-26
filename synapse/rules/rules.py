"""Rule definitions — deterministic conditions that trigger proactive agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from synapse.rules.state_store import EngineState


@dataclass
class Rule:
    """A single deterministic rule evaluated against EngineState.

    condition: pure function, no side effects, returns bool
    context_builder: packages relevant state into the event payload
    """

    id: str
    name: str
    description: str
    priority: int  # 1 (critical) → 10 (background)
    condition: Callable[["EngineState"], bool]
    action_id: str
    cooldown_minutes: int = 60
    context_builder: Callable[["EngineState"], dict] = field(
        default_factory=lambda: lambda s: {}
    )


# ---------------------------------------------------------------------------
# Rule: CVE detected for a dependency and a deploy is within 2 hours
# ---------------------------------------------------------------------------

def _cve_deploy_condition(state: "EngineState") -> bool:
    now = datetime.now(timezone.utc)
    dep_names = {d.name.lower() for d in state.dependencies.values()}
    if not dep_names:
        return False

    matching_cves = [
        cve for cve in state.cve_entries
        if cve.package.lower() in dep_names
    ]
    if not matching_cves:
        return False

    upcoming_deploys = [
        e for e in state.upcoming_events
        if "deploy" in e.tags
        and 0 <= (e.start - now).total_seconds() <= 7200
    ]
    return bool(upcoming_deploys)


def _cve_deploy_context(state: "EngineState") -> dict:
    now = datetime.now(timezone.utc)
    dep_names = {d.name.lower(): d for d in state.dependencies.values()}
    matching_cves = [
        cve for cve in state.cve_entries
        if cve.package.lower() in dep_names
    ]
    deploys = [
        e for e in state.upcoming_events
        if "deploy" in e.tags
        and 0 <= (e.start - now).total_seconds() <= 7200
    ]
    minutes_to_deploy = int((deploys[0].start - now).total_seconds() / 60) if deploys else 0
    return {
        "rule_id": "cve_before_deploy",
        "cves": [
            {"id": c.id, "package": c.package, "severity": c.severity, "description": c.description}
            for c in matching_cves
        ],
        "deploy_event": deploys[0].summary if deploys else "Unknown deploy",
        "minutes_to_deploy": minutes_to_deploy,
        "affected_packages": list({c.package for c in matching_cves}),
        "workspace": state.active_workspace,
    }


# ---------------------------------------------------------------------------
# Rule: CVE detected in any active dependency (no deploy needed)
# ---------------------------------------------------------------------------

def _new_cve_condition(state: "EngineState") -> bool:
    dep_names = {d.name.lower() for d in state.dependencies.values()}
    if not dep_names:
        return False
    return any(cve.package.lower() in dep_names for cve in state.cve_entries)


def _new_cve_context(state: "EngineState") -> dict:
    dep_names = {d.name.lower() for d in state.dependencies.values()}
    matching = [c for c in state.cve_entries if c.package.lower() in dep_names]
    return {
        "rule_id": "new_cve_in_active_dep",
        "cves": [
            {"id": c.id, "package": c.package, "severity": c.severity, "description": c.description}
            for c in matching
        ],
        "affected_packages": list({c.package for c in matching}),
        "workspace": state.active_workspace,
    }


# ---------------------------------------------------------------------------
# Rule: Deploy approaching but no recent file activity (possible forgotten checks)
# ---------------------------------------------------------------------------

def _deploy_approaching_condition(state: "EngineState") -> bool:
    now = datetime.now(timezone.utc)
    return any(
        "deploy" in e.tags and 0 <= (e.start - now).total_seconds() <= 3600
        for e in state.upcoming_events
    )


def _deploy_approaching_context(state: "EngineState") -> dict:
    now = datetime.now(timezone.utc)
    deploys = [
        e for e in state.upcoming_events
        if "deploy" in e.tags and 0 <= (e.start - now).total_seconds() <= 3600
    ]
    minutes_to_deploy = int((deploys[0].start - now).total_seconds() / 60) if deploys else 0
    return {
        "rule_id": "deploy_approaching",
        "deploy_event": deploys[0].summary if deploys else "Unknown deploy",
        "minutes_to_deploy": minutes_to_deploy,
        "last_changed_file": state.last_changed_file,
        "workspace": state.active_workspace,
    }


# ---------------------------------------------------------------------------
# RULES registry — ordered by priority (lower = higher priority)
# ---------------------------------------------------------------------------

RULES: list[Rule] = [
    Rule(
        id="cve_before_deploy",
        name="CVE Detected Before Deploy",
        description=(
            "A dependency with a known CVE is active and a deploy is scheduled "
            "within 120 minutes. Immediate attention required."
        ),
        priority=1,
        condition=_cve_deploy_condition,
        action_id="security_advisory",
        cooldown_minutes=30,
        context_builder=_cve_deploy_context,
    ),
    Rule(
        id="new_cve_in_active_dep",
        name="New CVE in Active Dependency",
        description="A CVE was published for a package currently in the active workspace.",
        priority=2,
        condition=_new_cve_condition,
        action_id="security_advisory",
        cooldown_minutes=120,
        context_builder=_new_cve_context,
    ),
    Rule(
        id="deploy_approaching",
        name="Deploy Approaching",
        description="A deploy event is within 60 minutes. Verify readiness.",
        priority=3,
        condition=_deploy_approaching_condition,
        action_id="ops_advisory",
        cooldown_minutes=45,
        context_builder=_deploy_approaching_context,
    ),
]
