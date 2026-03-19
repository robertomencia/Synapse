"""Security Agent — detects credentials and sensitive patterns in files."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from synapse.agents.base import AgentOutput, BaseAgent
from synapse.event_bus import SynapseEvent
from synapse.memory.models import AgentAction, Observation

logger = logging.getLogger(__name__)

SENSITIVE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("API Key", re.compile(r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[\w\-]{16,}')),
    ("Secret", re.compile(r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\']?\S{8,}')),
    ("AWS Key", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("Private Key", re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ("JWT Token", re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')),
    ("Bearer Token", re.compile(r'(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}')),
    ("Database URL", re.compile(r'(?i)(postgres|mysql|mongodb|redis)://[^\s"\'<>]+')),
]

IGNORED_PATHS = {".env.example", ".env.template", "test", "mock", "fixture", "fake"}


class SecurityAgent(BaseAgent):
    name = "security"
    subscribes_to = ["file.changed", "file.created"]

    async def process(self, event: SynapseEvent) -> AgentOutput:
        path = event.payload.get("path", "")
        preview = event.payload.get("preview", "")

        if not preview or not path:
            return self._idle()

        path_obj = Path(path)

        # Skip test files and templates
        path_lower = str(path_obj).lower()
        if any(ignored in path_lower for ignored in IGNORED_PATHS):
            return self._idle()

        findings: list[str] = []
        for name, pattern in SENSITIVE_PATTERNS:
            if pattern.search(preview):
                findings.append(name)

        if not findings:
            return self._idle()

        summary = f"ALERT: Sensitive data in {path_obj.name}: {', '.join(findings)}"
        detail = (
            f"File {path} contains patterns that look like credentials: {', '.join(findings)}. "
            f"Ensure this file is in .gitignore and never commit secrets to version control."
        )

        obs = Observation(
            text=summary,
            source=self.name,
            event_type=event.type,
            metadata={"path": path, "findings": findings},
        )
        await self._memory.store_observation(obs)

        action_record = AgentAction(
            agent_name=self.name,
            action_type="alert",
            summary=summary,
            detail=detail,
            confidence=0.9,
            suggested_actions=[
                f"Add {path_obj.name} to .gitignore",
                "Use environment variables instead of hardcoded secrets",
                "Rotate the exposed credentials immediately if committed",
            ],
            metadata={"path": path, "findings": findings},
        )
        await self._memory.store_action(action_record)

        return AgentOutput(
            agent_name=self.name,
            status="alert",
            summary=summary,
            detail=detail,
            confidence=0.9,
            suggested_actions=action_record.suggested_actions,
            metadata={"path": path, "findings": findings},
        )
