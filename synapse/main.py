"""Synapse bootstrap — wires all layers and runs the event loop."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from synapse.config import settings
from synapse.event_bus import bus

logger = logging.getLogger(__name__)


async def run(hud: bool | None = None) -> None:
    """Bootstrap and run Synapse."""
    settings.ensure_dirs()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info("◈ Synapse starting up...")

    # 1. Memory
    from synapse.memory.memory_manager import MemoryManager
    memory = MemoryManager(settings.chroma_path, settings.sqlite_path)
    memory.connect()
    logger.info("Memory layer connected (ChromaDB + SQLite)")

    # 2. LLM
    from synapse.llm.ollama_client import OllamaClient
    llm = OllamaClient(
        base_url=settings.ollama_url,
        model=settings.ollama_model,
        fallback_model=settings.ollama_fallback_model,
    )
    llm_ok = await llm.is_available()
    if not llm_ok:
        logger.warning("Ollama not available at %s — agents will run in degraded mode", settings.ollama_url)
    else:
        logger.info("LLM connected: %s", settings.ollama_model)

    # 3. Agents
    from synapse.agents.dev_agent import DevAgent
    from synapse.agents.security_agent import SecurityAgent
    from synapse.agents.ops_agent import OpsAgent
    from synapse.agents.life_agent import LifeAgent

    agents = [
        DevAgent(memory, llm),
        SecurityAgent(memory, llm),
        OpsAgent(memory, llm, poll_interval=60),
        LifeAgent(memory, llm),
    ]
    ops_agent = agents[2]  # type: ignore[index]

    # 4. Orchestrator
    from synapse.orchestrator.graph import Orchestrator
    orchestrator = Orchestrator(agents, memory)
    orchestrator.subscribe_to_bus()
    logger.info("Orchestrator ready with %d agents", len(agents))

    # 5. Start event bus
    await bus.start()

    # 6. HUD
    use_hud = hud if hud is not None else settings.hud_enabled
    hud_app = None
    if use_hud:
        try:
            from synapse.hud.app import HUDApp
            hud_app = HUDApp()
            hud_app.start(asyncio.get_running_loop())
            logger.info("HUD overlay started")
        except Exception as e:
            logger.warning("HUD failed to start: %s", e)

    # 7. Perception sensors
    watch_paths = settings.get_watch_paths()
    existing_paths = [p for p in watch_paths if p.exists()]
    logger.info("Watching paths: %s", existing_paths)

    from synapse.perception.file_watcher import FileWatcher
    from synapse.perception.screen_capture import ScreenCapture
    from synapse.perception.vscode_context import VSCodeContext

    sensors = [
        FileWatcher(existing_paths, warmup_delay=settings.file_watcher_warmup_delay),
        ScreenCapture(interval=settings.screen_capture_interval),
        VSCodeContext(interval=10),
    ]

    # 8. Rule Engine — proactive, deterministic layer
    from synapse.rules.state_store import StateStore
    from synapse.rules.engine import RuleEngine
    from synapse.rules.rules import RULES
    from synapse.collectors.dependency_collector import DependencyCollector
    from synapse.collectors.rss_collector import RSSCollector
    from synapse.collectors.calendar_collector import CalendarCollector
    from synapse.agents.proactive_agent import ProactiveAgent

    state_store = StateStore()

    # Wire ProactiveAgent into the orchestrator
    proactive_agent = ProactiveAgent(memory, llm)
    agents.append(proactive_agent)
    bus.subscribe("rule.*", orchestrator.handle)
    logger.info("ProactiveAgent registered, orchestrator subscribed to rule.* events")

    # Collectors
    collectors = []

    initial_workspace = existing_paths[0] if existing_paths else None
    dep_collector = DependencyCollector(state_store, initial_workspace=initial_workspace)
    collectors.append(dep_collector)

    extra_urls = [u.strip() for u in settings.rss_extra_feed_urls.split(",") if u.strip()]
    rss_collector = RSSCollector(
        state_store,
        extra_feed_urls=extra_urls or None,
        poll_interval=settings.rss_poll_interval,
    )
    collectors.append(rss_collector)

    ics_path_str = settings.calendar_ics_path.strip()
    if ics_path_str:
        ics_path = Path(ics_path_str).expanduser().resolve()
        if ics_path.exists():
            cal_collector = CalendarCollector(
                state_store,
                ics_path=ics_path,
                poll_interval=60,
                lookahead_hours=settings.calendar_lookahead_hours,
            )
            collectors.append(cal_collector)
            logger.info("CalendarCollector enabled: %s", ics_path)
        else:
            logger.warning("CALENDAR_ICS_PATH set but file not found: %s", ics_path)
    else:
        logger.info("CalendarCollector disabled (set CALENDAR_ICS_PATH in .env to enable)")

    rule_engine = RuleEngine(
        state_store,
        RULES,
        eval_interval=settings.rule_engine_eval_interval,
    )

    # 9. Start everything
    tasks: list[asyncio.Task] = []
    for sensor in sensors:
        tasks.append(asyncio.create_task(sensor.start()))

    tasks.append(asyncio.create_task(ops_agent.start_polling()))

    for collector in collectors:
        tasks.append(asyncio.create_task(collector.start()))

    if settings.rule_engine_enabled:
        tasks.append(asyncio.create_task(rule_engine.start()))
        logger.info("RuleEngine started with %d rules (eval every %ds)",
                    len(RULES), settings.rule_engine_eval_interval)

    logger.info("◈ Synapse is alive. Watching. Acting. Proactively.")

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down Synapse...")
        for task in tasks:
            task.cancel()
        for sensor in sensors:
            await sensor.stop()
        for collector in collectors:
            await collector.stop()
        if settings.rule_engine_enabled:
            await rule_engine.stop()
        await bus.stop()
        await llm.close()
        memory.close()
        if hud_app:
            hud_app.stop()
        logger.info("Synapse stopped. Goodbye.")


def main(hud: bool | None = None) -> None:
    asyncio.run(run(hud=hud))
