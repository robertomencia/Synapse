"""Rule Engine — deterministic evaluation loop that drives proactive behavior."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from synapse.event_bus import SynapseEvent, bus
from synapse.rules.rules import Rule
from synapse.rules.state_store import EngineState, StateStore

logger = logging.getLogger(__name__)


class RuleEngine:
    """Evaluates rules against StateStore every eval_interval seconds.

    This is the proactive core of Synapse: deterministic, auditable, LLM-free.
    When a rule fires, it publishes a 'rule.fired' event — the ProactiveAgent
    picks it up and generates the human-readable response via LLM.
    """

    def __init__(
        self,
        state_store: StateStore,
        rules: list[Rule],
        eval_interval: int = 30,
    ) -> None:
        self._store = state_store
        # Sort by priority so critical rules always evaluate first
        self._rules = sorted(rules, key=lambda r: r.priority)
        self._eval_interval = eval_interval
        self._fire_history: dict[str, datetime] = {}
        self._running = False
        self._total_fires = 0

    async def start(self) -> None:
        self._running = True
        logger.info(
            "RuleEngine started: %d rules, eval every %ds",
            len(self._rules),
            self._eval_interval,
        )
        while self._running:
            await asyncio.sleep(self._eval_interval)
            await self._evaluate_all()

    async def stop(self) -> None:
        self._running = False

    async def _evaluate_all(self) -> None:
        try:
            state = await self._store.snapshot()
        except Exception as e:
            logger.error("RuleEngine: failed to get state snapshot: %s", e)
            return

        for rule in self._rules:
            if self._is_on_cooldown(rule):
                continue
            try:
                if rule.condition(state):
                    await self._fire(rule, state)
            except Exception as e:
                logger.warning("Rule '%s' condition raised an exception: %s", rule.id, e)

    def _is_on_cooldown(self, rule: Rule) -> bool:
        last = self._fire_history.get(rule.id)
        if last is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed < rule.cooldown_minutes * 60

    async def _fire(self, rule: Rule, state: EngineState) -> None:
        try:
            context = rule.context_builder(state)
        except Exception as e:
            logger.warning("Rule '%s' context_builder failed: %s", rule.id, e)
            context = {"rule_id": rule.id, "error": str(e)}

        self._fire_history[rule.id] = datetime.now(timezone.utc)
        self._total_fires += 1

        logger.info(
            "◈ Rule fired: [%s] '%s' (priority=%d, fire #%d)",
            rule.id,
            rule.name,
            rule.priority,
            self._total_fires,
        )

        event = SynapseEvent(
            type="rule.fired",
            source="rule_engine",
            payload={
                "rule_id": rule.id,
                "rule_name": rule.name,
                "rule_description": rule.description,
                "action_id": rule.action_id,
                "priority": rule.priority,
                "context": context,
            },
            priority=rule.priority,
        )
        await bus.publish(event)

    def cooldown_status(self) -> dict[str, float]:
        """Return remaining cooldown seconds per rule (for debugging/status)."""
        now = datetime.now(timezone.utc)
        result = {}
        for rule in self._rules:
            last = self._fire_history.get(rule.id)
            if last is None:
                result[rule.id] = 0.0
            else:
                elapsed = (now - last).total_seconds()
                remaining = max(0.0, rule.cooldown_minutes * 60 - elapsed)
                result[rule.id] = remaining
        return result
