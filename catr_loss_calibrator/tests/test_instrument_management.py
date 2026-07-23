from __future__ import annotations

import socket

from catr_loss_calibrator.instrument_management.connection_service import InstrumentConnectionService
from catr_loss_calibrator.instrument_management.instrument_management_service import InstrumentManagementService
from catr_loss_calibrator.instrument_management.models import InstrumentConnectionConfig
from catr_loss_calibrator.instrument_management.recovery import ConnectionRecoveryPolicy
from catr_loss_calibrator.instrument_management.resource_lock import ResourceLock
from catr_loss_calibrator.hardware.link_box.lcd74000f import Lcd74000fLinkBox
from catr_loss_calibrator.hardware.mock import MockLinkBox, MockVna


def test_instrument_connection_service_snapshot_reports_mocks() -> None:
    service = InstrumentConnectionService.mock()
    vna_state, link_box_state = service.snapshot()
    assert vna_state.is_connected is False
    assert link_box_state.is_connected is False


def test_instrument_management_service_enforces_resource_lock() -> None:
    lock = ResourceLock()
    lock.acquire("VNA", "owner-a")
    try:
        lock.acquire("VNA", "owner-b")
    except RuntimeError as exc:
        assert "already owned" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_instrument_management_service_connects_and_snapshots() -> None:
    service = InstrumentManagementService.mock()
    vna_state, link_box_state = service.connect_all()
    assert vna_state.is_connected is True
    assert link_box_state.is_connected is True
    service.disconnect_all()
    vna_state, link_box_state = service.snapshot()
    assert vna_state.is_connected is False
    assert link_box_state.is_connected is False


def test_from_configs_can_build_mock_and_real_capable_services() -> None:
    service = InstrumentConnectionService.from_configs(
        vna_config=InstrumentConnectionConfig(resource="MOCK::VNA", model="MOCK-VNA", use_mock=True),
        link_box_config=InstrumentConnectionConfig(resource="MOCK::LINKBOX", model="MOCK-LINKBOX", use_mock=True),
    )
    vna_state, link_box_state = service.snapshot()
    assert vna_state.model == ""
    assert link_box_state.model == ""


def test_connection_service_rolls_back_on_partial_failure() -> None:
    class FailingLinkBox(MockLinkBox):
        def connect(self):  # type: ignore[override]
            super().connect()
            raise RuntimeError("boom")

    service = InstrumentConnectionService(vna=MockVna(), link_box=FailingLinkBox())
    try:
        service.connect_all()
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
    vna_state, link_box_state = service.snapshot()
    assert vna_state.is_connected is False
    assert link_box_state.is_connected is False


def test_connection_service_can_retry_after_failure() -> None:
    class FlakyLinkBox(MockLinkBox):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def connect(self):  # type: ignore[override]
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary")
            return super().connect()

    service = InstrumentConnectionService(
        vna=MockVna(),
        link_box=FlakyLinkBox(),
        recovery_policy=ConnectionRecoveryPolicy(max_retries=1, retry_delay_ms=0),
    )
    vna_info, link_box_info = service.connect_all()
    assert vna_info.model == "MOCK-VNA"
    assert link_box_info.model == "LCD74000F-MOCK"


def test_lcd74000f_link_box_uses_native_socket_for_tcpip_socket_resource(monkeypatch) -> None:
    class FakeSocket:
        def __init__(self) -> None:
            self.timeout = 0.0
            self.sent: list[bytes] = []
            self.responses = [b"LCD74000F,OK\n"]
            self.closed = False

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def sendall(self, payload: bytes) -> None:
            self.sent.append(payload)

        def recv(self, _size: int) -> bytes:
            if not self.responses:
                raise socket.timeout()
            return self.responses.pop(0)

        def close(self) -> None:
            self.closed = True

    fake_socket = FakeSocket()
    captured: dict[str, object] = {}

    def fake_create_connection(endpoint, timeout=None):
        captured["endpoint"] = endpoint
        captured["timeout"] = timeout
        return fake_socket

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    link_box = Lcd74000fLinkBox(resource="TCPIP0::192.168.1.113::7::SOCKET", timeout_ms=2500)

    info = link_box.connect()
    query_response = link_box.send_command("*IDN?")
    write_response = link_box.send_command("CONFigure:LINK H/V, SG")
    link_box.disconnect()

    assert captured == {"endpoint": ("192.168.1.113", 7), "timeout": 2.5}
    assert info.model == "LCD74000F RAW-SOCKET"
    assert query_response == "LCD74000F,OK"
    assert write_response == "OK"
    assert fake_socket.sent == [b"*IDN?\n", b"CONFigure:LINK H/V, SG\n"]
    assert fake_socket.closed is True


def test_lcd74000f_link_box_accepts_plain_ip_port_resource(monkeypatch) -> None:
    class FakeSocket:
        def __init__(self) -> None:
            self.responses = [b"LCD74000F,OK\n"]
            self.sent: list[bytes] = []

        def settimeout(self, _timeout: float) -> None:
            pass

        def sendall(self, payload: bytes) -> None:
            self.sent.append(payload)

        def recv(self, _size: int) -> bytes:
            return self.responses.pop(0)

        def close(self) -> None:
            pass

    fake_socket = FakeSocket()
    captured: dict[str, object] = {}

    def fake_create_connection(endpoint, timeout=None):
        captured["endpoint"] = endpoint
        captured["timeout"] = timeout
        return fake_socket

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    link_box = Lcd74000fLinkBox(resource="192.168.1.113:7", timeout_ms=1500)

    info = link_box.connect()

    assert captured == {"endpoint": ("192.168.1.113", 7), "timeout": 1.5}
    assert info.resource == "192.168.1.113:7"
    assert info.model == "LCD74000F RAW-SOCKET"


def test_lcd74000f_link_box_rejects_non_ip_port_resource_without_visa() -> None:
    link_box = Lcd74000fLinkBox(resource="USB0::LCD74000F::INSTR", timeout_ms=1500)

    try:
        link_box.connect()
    except RuntimeError as exc:
        assert "IP address and TCP port" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_connection_service_passes_link_box_ip_and_port_to_controller(monkeypatch) -> None:
    class FakeSocket:
        def settimeout(self, _timeout: float) -> None:
            pass

        def sendall(self, _payload: bytes) -> None:
            pass

        def recv(self, _size: int) -> bytes:
            return b"LCD74000F,OK\n"

        def close(self) -> None:
            pass

    captured: dict[str, object] = {}

    def fake_create_connection(endpoint, timeout=None):
        captured["endpoint"] = endpoint
        captured["timeout"] = timeout
        return FakeSocket()

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    service = InstrumentConnectionService.from_configs(
        vna_config=InstrumentConnectionConfig(resource="MOCK::VNA", model="MOCK-VNA", use_mock=True),
        link_box_config=InstrumentConnectionConfig(
            resource="",
            model="LCD74000F",
            use_mock=False,
            timeout_ms=2500,
            ip_address="192.168.1.113",
            tcp_port=7,
        ),
    )

    service.link_box.connect()

    assert captured == {"endpoint": ("192.168.1.113", 7), "timeout": 2.5}
