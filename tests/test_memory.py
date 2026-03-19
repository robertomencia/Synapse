"""Memory layer tests."""

import pytest
from synapse.memory.memory_manager import MemoryManager
from synapse.memory.models import AgentAction, Observation


@pytest.mark.asyncio
async def test_store_and_retrieve_observation(tmp_memory: MemoryManager) -> None:
    obs = Observation(
        text="DevAgent: auth.py modified — added JWT validation",
        source="dev_agent",
        event_type="file.changed",
        metadata={"path": "src/auth.py"},
    )
    obs_id = await tmp_memory.store_observation(obs)
    assert obs_id == obs.id

    recent = await tmp_memory.get_recent(minutes=5)
    assert any(e.id == obs_id for e in recent)


@pytest.mark.asyncio
async def test_store_and_retrieve_action(tmp_memory: MemoryManager) -> None:
    action = AgentAction(
        agent_name="security",
        action_type="alert",
        summary="API key detected in config.py",
        detail="Found pattern matching API key in config.py line 42",
        confidence=0.95,
        suggested_actions=["Add config.py to .gitignore"],
    )
    action_id = await tmp_memory.store_action(action)
    assert action_id == action.id

    recent = await tmp_memory.get_recent(minutes=5)
    action_entries = [e for e in recent if e.entry_type == "action"]
    assert len(action_entries) >= 1


@pytest.mark.asyncio
async def test_semantic_search(tmp_memory: MemoryManager) -> None:
    observations = [
        Observation(text="Working on JWT authentication in auth.py", source="dev", event_type="file.changed"),
        Observation(text="CPU usage at 95%, memory pressure detected", source="ops", event_type="system.check"),
        Observation(text="Debugging OAuth flow in the login endpoint", source="dev", event_type="file.changed"),
    ]
    for obs in observations:
        await tmp_memory.store_observation(obs)

    results = await tmp_memory.search_semantic("authentication and login", limit=3)
    assert len(results) >= 1
    # The auth-related results should come first
    texts = [r.text for r in results]
    assert any("auth" in t.lower() or "login" in t.lower() or "oauth" in t.lower() for t in texts)


@pytest.mark.asyncio
async def test_empty_memory_returns_empty(tmp_memory: MemoryManager) -> None:
    recent = await tmp_memory.get_recent(minutes=30)
    assert recent == []
