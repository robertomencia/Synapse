"""Event bus tests."""

import asyncio
import pytest
from synapse.event_bus import EventBus, SynapseEvent


@pytest.mark.asyncio
async def test_subscribe_and_receive() -> None:
    eb = EventBus()
    await eb.start()
    received: list[SynapseEvent] = []

    async def handler(event: SynapseEvent) -> None:
        received.append(event)

    eb.subscribe("file.*", handler)

    event = SynapseEvent(type="file.changed", source="test", payload={"path": "foo.py"})
    await eb.publish(event)
    await asyncio.sleep(0.1)

    assert len(received) == 1
    assert received[0].id == event.id
    await eb.stop()


@pytest.mark.asyncio
async def test_wildcard_matching() -> None:
    eb = EventBus()
    await eb.start()
    received: list[str] = []

    async def handler(event: SynapseEvent) -> None:
        received.append(event.type)

    eb.subscribe("agent.output.*", handler)

    await eb.publish(SynapseEvent(type="agent.output.dev", source="orchestrator", payload={}))
    await eb.publish(SynapseEvent(type="agent.output.security", source="orchestrator", payload={}))
    await eb.publish(SynapseEvent(type="file.changed", source="watcher", payload={}))
    await asyncio.sleep(0.1)

    assert "agent.output.dev" in received
    assert "agent.output.security" in received
    assert "file.changed" not in received
    await eb.stop()
