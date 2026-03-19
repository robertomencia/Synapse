"""Security Agent tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from synapse.agents.security_agent import SecurityAgent
from synapse.event_bus import SynapseEvent


@pytest.fixture
def security_agent(tmp_memory):
    llm = MagicMock()
    return SecurityAgent(tmp_memory, llm)


@pytest.mark.asyncio
async def test_detects_api_key(security_agent: SecurityAgent) -> None:
    event = SynapseEvent(
        type="file.changed",
        source="file_watcher",
        payload={
            "path": "/projects/myapp/config.py",
            "extension": ".py",
            "action": "modified",
            "preview": 'API_KEY = "sk-abc123xyz789longkeyhere12345678"',
        },
    )
    output = await security_agent.process(event)
    assert output.status == "alert"
    assert "API Key" in output.summary or "Sensitive" in output.summary


@pytest.mark.asyncio
async def test_ignores_clean_file(security_agent: SecurityAgent) -> None:
    event = SynapseEvent(
        type="file.changed",
        source="file_watcher",
        payload={
            "path": "/projects/myapp/utils.py",
            "extension": ".py",
            "action": "modified",
            "preview": "def add(a, b):\n    return a + b\n",
        },
    )
    output = await security_agent.process(event)
    assert output.status == "idle"


@pytest.mark.asyncio
async def test_ignores_test_files(security_agent: SecurityAgent) -> None:
    event = SynapseEvent(
        type="file.changed",
        source="file_watcher",
        payload={
            "path": "/projects/myapp/tests/test_auth.py",
            "extension": ".py",
            "action": "modified",
            "preview": 'FAKE_API_KEY = "sk-abc123xyz789longkeyhere12345678"',
        },
    )
    output = await security_agent.process(event)
    assert output.status == "idle"


@pytest.mark.asyncio
async def test_detects_private_key(security_agent: SecurityAgent) -> None:
    event = SynapseEvent(
        type="file.changed",
        source="file_watcher",
        payload={
            "path": "/projects/myapp/keys/id_rsa",
            "extension": "",
            "action": "created",
            "preview": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...",
        },
    )
    output = await security_agent.process(event)
    assert output.status == "alert"
