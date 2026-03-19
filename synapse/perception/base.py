"""Base Sensor protocol."""

from abc import ABC, abstractmethod


class Sensor(ABC):
    """A perception sensor that emits events to the event bus."""

    @abstractmethod
    async def start(self) -> None:
        """Start the sensor and begin publishing events."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the sensor gracefully."""
