"""Proactive Agent — LLM executor for rule-fired events."""

from __future__ import annotations

import json
import logging
import re

from synapse.agents.base import AgentOutput, BaseAgent
from synapse.event_bus import SynapseEvent
from synapse.memory.models import AgentAction, Observation

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Synapse's proactive security and operations advisor.
You have been triggered by an automated rule-based monitoring system — NOT by the user.
Your role is to clearly explain the detected situation and give specific, actionable recommendations.

Be direct and urgent when severity demands it. Do NOT pad your response.

Respond with a valid JSON object only:
{
  "summary": "<one sentence, shown in HUD notification>",
  "detail": "<2-4 sentences explaining the situation and risk>",
  "actions": ["<action 1>", "<action 2>", "<action 3>"],
  "confidence": <0.0-1.0>
}"""

_ACTION_PROMPTS: dict[str, str] = {
    "security_advisory": """\
AUTOMATED RULE TRIGGER: {rule_name}

{rule_description}

Detected CVEs:
{cve_list}

Affected packages: {affected_packages}
Deploy scheduled in: {minutes_to_deploy} minutes
Workspace: {workspace}

Explain the risk clearly and give concrete steps the developer should take before deploying.\
""",
    "ops_advisory": """\
AUTOMATED RULE TRIGGER: {rule_name}

{rule_description}

Deploy event: {deploy_event}
Time until deploy: {minutes_to_deploy} minutes
Last file changed: {last_changed_file}
Workspace: {workspace}

What operational checks or preparation should happen before this deploy?\
""",
}

_DEFAULT_PROMPT = """\
AUTOMATED RULE TRIGGER: {rule_name}

{rule_description}

Context: {context}

Explain what was detected and what the developer should do.\
"""


def _format_cve_list(cves: list[dict]) -> str:
    if not cves:
        return "None"
    lines = []
    for cve in cves:
        severity = cve.get("severity", "unknown").upper()
        desc = cve.get("description", "")
        lines.append(f"  - {cve['id']} [{severity}] in {cve['package']}: {desc}")
    return "\n".join(lines)


def _build_prompt(action_id: str, rule_name: str, rule_description: str, context: dict) -> str:
    template = _ACTION_PROMPTS.get(action_id, _DEFAULT_PROMPT)
    cves = context.get("cves", [])
    return template.format(
        rule_name=rule_name,
        rule_description=rule_description,
        cve_list=_format_cve_list(cves),
        affected_packages=", ".join(context.get("affected_packages", [])) or "N/A",
        minutes_to_deploy=context.get("minutes_to_deploy", "N/A"),
        deploy_event=context.get("deploy_event", "N/A"),
        last_changed_file=context.get("last_changed_file", "N/A"),
        workspace=context.get("workspace", "N/A"),
        context=json.dumps(context, default=str, indent=2),
    )


def _parse_llm_response(raw: str) -> dict:
    """Extract JSON from LLM response, tolerating markdown fences."""
    # Strip ```json ... ``` fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: extract first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


class ProactiveAgent(BaseAgent):
    """Handles rule.fired events: prepares context, calls LLM, emits alert."""

    name = "proactive"
    subscribes_to = ["rule.fired"]

    async def process(self, event: SynapseEvent) -> AgentOutput:
        rule_id = event.payload.get("rule_id", "unknown")
        rule_name = event.payload.get("rule_name", "Unknown Rule")
        rule_description = event.payload.get("rule_description", "")
        action_id = event.payload.get("action_id", "security_advisory")
        priority = event.payload.get("priority", 5)
        context = event.payload.get("context", {})

        prompt = _build_prompt(action_id, rule_name, rule_description, context)

        parsed: dict = {}
        try:
            raw = await self._llm.complete(prompt, system=_SYSTEM_PROMPT)
            parsed = _parse_llm_response(raw)
        except Exception as e:
            logger.warning("ProactiveAgent: LLM call failed for rule '%s': %s", rule_id, e)

        # Graceful degradation: emit deterministic alert even without LLM
        if not parsed.get("summary"):
            cves = context.get("cves", [])
            cve_ids = ", ".join(c["id"] for c in cves) if cves else ""
            minutes = context.get("minutes_to_deploy", "")
            if cve_ids and minutes:
                summary = f"ALERT: {cve_ids} in active dependencies — deploy in {minutes}min"
            elif cve_ids:
                summary = f"ALERT: {cve_ids} detected in active dependencies"
            else:
                summary = f"ALERT: {rule_name}"

            parsed = {
                "summary": summary,
                "detail": (
                    f"Automated rule '{rule_id}' fired. "
                    f"{rule_description} "
                    f"Review context and take action before proceeding."
                ),
                "actions": [
                    "Review the flagged packages for the reported CVE",
                    "Check if a patched version is available",
                    "Consider delaying the deploy until patched",
                ],
                "confidence": 0.7,
            }

        summary = parsed.get("summary", f"Rule alert: {rule_name}")
        detail = parsed.get("detail", "")
        actions = parsed.get("actions", [])
        confidence = float(parsed.get("confidence", 0.85))

        # Store in memory
        obs = Observation(
            text=f"[RULE:{rule_id}] {summary}",
            source=self.name,
            event_type=event.type,
            metadata={"rule_id": rule_id, "action_id": action_id, "context": context},
        )
        try:
            await self._memory.store_observation(obs)
        except Exception as e:
            logger.debug("ProactiveAgent: memory store failed: %s", e)

        try:
            agent_action = AgentAction(
                agent_name=self.name,
                action_type="alert",
                description=detail,
                confidence=confidence,
                suggested_actions=actions,
                metadata={"rule_id": rule_id, "priority": priority},
            )
            await self._memory.store_action(agent_action)
        except Exception as e:
            logger.debug("ProactiveAgent: action store failed: %s", e)

        return AgentOutput(
            agent_name=self.name,
            status="alert",
            summary=summary,
            detail=detail,
            confidence=confidence,
            suggested_actions=actions,
            metadata={"rule_id": rule_id, "action_id": action_id, "priority": priority},
        )
