"""Dev Agent — analyzes code changes autonomously."""

from __future__ import annotations

import logging
from pathlib import Path

from synapse.agents.base import AgentOutput, BaseAgent
from synapse.event_bus import SynapseEvent
from synapse.memory.models import AgentAction, Observation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Dev Agent inside Synapse, an AI that observes a developer's environment.
You receive a code file change and must analyze it briefly and helpfully.
Be concise. Focus on: what changed, potential issues, or useful context.
Output a JSON object with keys: "summary" (1 sentence), "detail" (2-3 sentences), "issues" (list of strings), "confidence" (0.0-1.0)."""

ANALYSIS_PROMPT = """A file was {action}: {path}

Extension: {ext}
Preview of content:
```
{preview}
```

Analyze this change. What is happening? Any issues or notable patterns?"""


class DevAgent(BaseAgent):
    name = "dev"
    subscribes_to = ["file.changed", "file.created", "vscode.context"]

    async def process(self, event: SynapseEvent) -> AgentOutput:
        if event.type == "vscode.context":
            return self._handle_vscode(event)

        return await self._handle_file_event(event)

    async def _handle_file_event(self, event: SynapseEvent) -> AgentOutput:
        path = event.payload.get("path", "")
        ext = event.payload.get("extension", "")
        action = event.payload.get("action", "changed")
        preview = event.payload.get("preview", "")

        if not preview:
            return self._idle()

        prompt = ANALYSIS_PROMPT.format(
            action=action, path=path, ext=ext, preview=preview[:800]
        )

        try:
            raw = await self._llm.complete(prompt, system=SYSTEM_PROMPT)
            parsed = self._parse_response(raw)
        except Exception as e:
            logger.warning("DevAgent LLM call failed: %s", e)
            parsed = {
                "summary": f"File {action}: {Path(path).name}",
                "detail": f"Could not analyze: {e}",
                "issues": [],
                "confidence": 0.3,
            }

        # Store the observation
        obs = Observation(
            text=f"[{action.upper()}] {path}: {parsed['summary']}",
            source=self.name,
            event_type=event.type,
            metadata={"path": path, "action": action, "issues": parsed.get("issues", [])},
        )
        await self._memory.store_observation(obs)

        # Store the agent action
        action_record = AgentAction(
            agent_name=self.name,
            action_type="insight",
            summary=parsed["summary"],
            detail=parsed["detail"],
            confidence=float(parsed.get("confidence", 0.8)),
            suggested_actions=parsed.get("issues", []),
            metadata={"path": path, "event_id": event.id},
        )
        await self._memory.store_action(action_record)

        return AgentOutput(
            agent_name=self.name,
            status="insight" if parsed.get("issues") else "insight",
            summary=parsed["summary"],
            detail=parsed["detail"],
            confidence=float(parsed.get("confidence", 0.8)),
            suggested_actions=parsed.get("issues", []),
            metadata={"path": path},
        )

    def _handle_vscode(self, event: SynapseEvent) -> AgentOutput:
        workspace = event.payload.get("workspace", "")
        return AgentOutput(
            agent_name=self.name,
            status="insight",
            summary=f"Working in: {Path(workspace).name if workspace else 'unknown'}",
            detail=f"VS Code workspace changed to: {workspace}",
            confidence=1.0,
        )

    def _parse_response(self, raw: str) -> dict:
        import json
        import re
        # Try to extract JSON from the response
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Fallback: treat the whole response as the detail
        return {
            "summary": raw[:100].strip(),
            "detail": raw.strip(),
            "issues": [],
            "confidence": 0.7,
        }
