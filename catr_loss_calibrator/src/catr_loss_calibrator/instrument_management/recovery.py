from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConnectionRecoveryPolicy:
    max_retries: int = 1
    retry_delay_ms: int = 200

    def validate(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.retry_delay_ms < 0:
            raise ValueError("retry_delay_ms must be >= 0")
