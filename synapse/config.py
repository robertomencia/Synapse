"""Centralized configuration via pydantic-settings."""

from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    ollama_fallback_model: str = "llama3"

    # Paths
    synapse_data_dir: Path = Path("./data")
    chroma_path: Path = Path("./data/chroma")
    sqlite_path: Path = Path("./data/synapse.db")

    # Perception
    watch_paths: str = "~/projects"
    screen_capture_interval: int = 5
    file_watcher_warmup_delay: int = 5

    # Features
    hud_enabled: bool = True
    voice_enabled: bool = False
    auto_act: bool = False

    # Memory
    memory_max_episodes: int = 10000
    memory_retention_days: int = 90

    # Rule Engine
    rule_engine_enabled: bool = True
    rule_engine_eval_interval: int = 30  # seconds between evaluations

    # Collectors
    rss_poll_interval: int = 300  # seconds (5 minutes)
    rss_extra_feed_urls: str = ""  # comma-separated extra Atom feed URLs
    calendar_ics_path: str = ""  # path to local .ics file; empty = disabled
    calendar_lookahead_hours: int = 4

    @field_validator("chroma_path", "sqlite_path", "synapse_data_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        return Path(v).expanduser().resolve()

    def get_watch_paths(self) -> list[Path]:
        return [Path(p.strip()).expanduser().resolve() for p in self.watch_paths.split(",")]

    def ensure_dirs(self) -> None:
        self.synapse_data_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
