from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo

logger = logging.getLogger(__name__)


class ScpiCommunicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScpiConnectionConfig:
    resource_name: str
    timeout_ms: int = 10_000
    read_termination: str = "\n"
    write_termination: str = "\n"
    retries: int = 2
    retry_delay_s: float = 0.2
    fallback_tcp_port: int = 5025


class VisaScpiSession:
    def __init__(
        self,
        config: ScpiConnectionConfig,
        resource_manager: Any | None = None,
    ) -> None:
        self._config = config
        self._resource_manager = resource_manager
        self._resource: Any | None = None

    @property
    def resource_name(self) -> str:
        if self._resource is None:
            return self._config.resource_name
        return str(getattr(self._resource, "resource_name", self._config.resource_name))

    @property
    def is_open(self) -> bool:
        return self._resource is not None

    def open(self) -> None:
        if self._resource is not None:
            return

        errors: list[str] = []
        try:
            if self._resource_manager is None:
                try:
                    import pyvisa
                except ImportError as exc:  # pragma: no cover - optional dependency
                    raise ScpiCommunicationError("pyvisa is required for VISA SCPI instruments.") from exc
                self._resource_manager = pyvisa.ResourceManager()
            for resource_name in self._candidate_resource_names(self._config.resource_name):
                try:
                    resource = self._resource_manager.open_resource(resource_name)
                    resource.timeout = self._config.timeout_ms
                    self._set_optional_attribute(resource, "read_termination", self._config.read_termination)
                    self._set_optional_attribute(resource, "write_termination", self._config.write_termination)
                    self._resource = resource
                    logger.info("Opened VISA resource: %s", resource_name)
                    return
                except Exception as exc:  # noqa: BLE001 - try next equivalent VISA address.
                    errors.append(f"{resource_name}: {exc}")
                    logger.warning("Failed to open VISA candidate %s: %s", resource_name, exc)
        except Exception as exc:  # noqa: BLE001 - instrument boundary wraps VISA backend errors.
            logger.exception("Failed to open VISA resource: %s", self._config.resource_name)
            raise ScpiCommunicationError(f"Failed to open VISA resource {self._config.resource_name}: {exc}") from exc

        raise ScpiCommunicationError("Failed to open VISA resource candidates: " + " | ".join(errors))

    def close(self) -> None:
        resource = self._resource
        self._resource = None
        if resource is None:
            return

        try:
            resource.close()
        except Exception:
            logger.exception("Failed while closing VISA resource: %s", self._config.resource_name)

    def write(self, command: str) -> None:
        self._execute_with_retries("write", command, lambda: self._require_resource().write(command))

    def query(self, command: str) -> str:
        return str(
            self._execute_with_retries(
                "query",
                command,
                lambda: self._require_resource().query(command),
                retry=False,
            )
        ).strip()

    def query_ascii_values(self, command: str) -> list[float]:
        resource = self._require_resource()
        query_ascii_values = getattr(resource, "query_ascii_values", None)
        if callable(query_ascii_values):
            result = self._execute_with_retries(
                "query_ascii_values",
                command,
                lambda: query_ascii_values(command),
                retry=False,
            )
            return list(result)
        response = self.query(command)
        normalized = response.replace("\n", ",").replace("\r", ",").replace(";", ",")
        return [float(value.strip()) for value in normalized.split(",") if value.strip()]

    def query_binary_values(self, command: str, datatype: str = "d", is_big_endian: bool = False) -> list[float]:
        resource = self._require_resource()
        query_binary_values = getattr(resource, "query_binary_values", None)
        if not callable(query_binary_values):
            raise ScpiCommunicationError("VISA resource does not support binary value queries.")
        result = self._execute_with_retries(
            "query_binary_values",
            command,
            lambda: query_binary_values(command, datatype=datatype, is_big_endian=is_big_endian),
            retry=False,
        )
        return list(result)

    def _require_resource(self) -> Any:
        if self._resource is None:
            raise ScpiCommunicationError(f"VISA resource is not open: {self._config.resource_name}")
        return self._resource

    def _candidate_resource_names(self, resource_name: str) -> list[str]:
        resource_name = str(resource_name).strip()
        candidates = [resource_name]
        match = re.match(r"^(TCPIP\d*)::([^:]+)::inst\d+::INSTR$", resource_name, flags=re.IGNORECASE)
        if match:
            prefix, host = match.groups()
            candidates.append(f"{prefix}::{host}::{int(self._config.fallback_tcp_port)}::SOCKET")
            candidates.append(f"{prefix}::{host}::hislip0::INSTR")
        return list(dict.fromkeys(candidates))

    def _execute_with_retries(self, operation: str, command: str, action, *, retry: bool = True):
        attempts = max(1, self._config.retries + 1) if retry else 1
        last_error: Exception | None = None
        retryable_errors = self._retryable_errors()
        for attempt in range(1, attempts + 1):
            try:
                return action()
            except retryable_errors as exc:
                last_error = exc
                logger.warning(
                    "SCPI %s failed on %s attempt %s/%s: command=%s error=%s",
                    operation,
                    self._config.resource_name,
                    attempt,
                    attempts,
                    command,
                    exc,
                )
                if attempt < attempts:
                    time.sleep(self._config.retry_delay_s)
            except Exception as exc:  # noqa: BLE001 - unknown backend errors should still be wrapped.
                last_error = exc
                logger.exception("Unexpected SCPI %s failure on %s: command=%s", operation, self._config.resource_name, command)
                if attempt < attempts:
                    time.sleep(self._config.retry_delay_s)

        raise ScpiCommunicationError(
            f"SCPI {operation} failed after {attempts} attempt(s) on "
            f"{self._config.resource_name}: {command}: {last_error}"
        ) from last_error

    @staticmethod
    def _retryable_errors() -> tuple[type[BaseException], ...]:
        errors: list[type[BaseException]] = [TimeoutError, OSError, ScpiCommunicationError]
        try:
            from pyvisa import VisaIOError
        except Exception:  # pragma: no cover - pyvisa is optional in unit tests.
            return tuple(errors)
        return tuple([VisaIOError, *errors])

    @staticmethod
    def _set_optional_attribute(resource: Any, name: str, value: Any) -> None:
        try:
            setattr(resource, name, value)
        except Exception:
            logger.debug("VISA resource does not accept %s=%r.", name, value, exc_info=True)


@dataclass
class PyVisaScpiInstrument:
    resource: str
    model: str = "UNKNOWN"
    timeout_ms: int = 10_000

    def __post_init__(self) -> None:
        self._connected = False
        self._session = VisaScpiSession(
            ScpiConnectionConfig(
                resource_name=self.resource,
                timeout_ms=self.timeout_ms,
            )
        )

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session.is_open

    def connect(self) -> InstrumentInfo:
        self._session.open()
        self._connected = True
        try:
            idn = self._session.query("*IDN?")
        except Exception:
            idn = self.model
        return InstrumentInfo(resource=self.resource, model=idn.split(",")[1] if "," in idn else self.model)

    def disconnect(self) -> None:
        self._session.close()
        self._connected = False

    def send_command(self, command: str) -> str:
        if not self.is_connected:
            raise RuntimeError("SCPI instrument is not connected.")
        if command.strip().endswith("?"):
            return self._session.query(command)
        self._session.write(command)
        return "OK"
