from __future__ import annotations

from dataclasses import dataclass
import re
import socket

from catr_loss_calibrator.hardware.interfaces import InstrumentInfo, LinkBox


_TCPIP_SOCKET_RE = re.compile(r"^TCPIP\d*::(?P<host>.+)::(?P<port>\d+)::SOCKET$", re.IGNORECASE)
_HOST_PORT_RE = re.compile(r"^(?P<host>[^:\s]+):(?P<port>\d+)$")
DEFAULT_LCD74000F_TCP_PORT = 7


@dataclass
class Lcd74000fLinkBox(LinkBox):
    resource: str = ""
    model: str = "LCD74000F"
    timeout_ms: int = 10_000
    command_terminator: str = "\n"
    ip_address: str = ""
    tcp_port: int | None = None

    def __post_init__(self) -> None:
        if not self.resource and self.ip_address:
            self.resource = f"{self.ip_address}:{self._effective_tcp_port}"
        self._connected = False
        self._socket: socket.socket | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        socket_endpoint = _tcpip_socket_endpoint(
            self.resource,
            ip_address=self.ip_address,
            tcp_port=self.tcp_port,
        )
        if socket_endpoint is not None:
            host, port = socket_endpoint
            timeout_s = max(float(self.timeout_ms) / 1000.0, 0.001)
            self._socket = socket.create_connection((host, port), timeout=timeout_s)
            self._socket.settimeout(timeout_s)
            self._connected = True
            self.resource = f"{host}:{port}"
            return InstrumentInfo(resource=self.resource, model=f"{self.model} RAW-SOCKET")

        raise RuntimeError("Link box requires IP address and TCP port, for example 192.168.1.113:7.")

    def disconnect(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None
        self._connected = False

    @property
    def _effective_tcp_port(self) -> int:
        return int(self.tcp_port or DEFAULT_LCD74000F_TCP_PORT)

    def send_command(self, command: str) -> str:
        if self._socket is not None:
            return self._send_socket_command(command)
        raise RuntimeError("Link box is not connected.")

    def _send_socket_command(self, command: str) -> str:
        if self._socket is None:
            raise RuntimeError("Link box raw socket is not connected.")
        command = command.strip()
        if not command:
            raise RuntimeError("Link box command is empty.")
        payload = (command + self.command_terminator).encode("utf-8")
        self._socket.sendall(payload)
        if command.endswith("?"):
            return self._read_socket_response()
        return "OK"

    def _read_socket_response(self) -> str:
        if self._socket is None:
            raise RuntimeError("Link box raw socket is not connected.")
        chunks: list[bytes] = []
        while True:
            try:
                chunk = self._socket.recv(4096)
            except TimeoutError:
                break
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk or b"\r" in chunk:
                break
        if not chunks:
            raise RuntimeError("Link box raw socket query timed out.")
        return b"".join(chunks).decode("utf-8", errors="replace").strip()


def _tcpip_socket_endpoint(
    resource: str,
    *,
    ip_address: str = "",
    tcp_port: int | None = None,
) -> tuple[str, int] | None:
    ip_address = ip_address.strip()
    if ip_address:
        return ip_address, int(tcp_port or DEFAULT_LCD74000F_TCP_PORT)

    resource = resource.strip()
    host_port = _HOST_PORT_RE.match(resource)
    if host_port is not None:
        return host_port.group("host"), int(host_port.group("port"))

    match = _TCPIP_SOCKET_RE.match(resource.strip())
    if match is None:
        return None
    return match.group("host"), int(match.group("port"))
