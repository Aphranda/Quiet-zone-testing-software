from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResourceLock:
    _owners: dict[str, str] = field(default_factory=dict)

    def acquire(self, resource: str, owner: str) -> None:
        current = self._owners.get(resource)
        if current and current != owner:
            raise RuntimeError(f"Resource {resource} is already owned by {current}.")
        self._owners[resource] = owner

    def release(self, resource: str, owner: str) -> None:
        if self._owners.get(resource) == owner:
            del self._owners[resource]

