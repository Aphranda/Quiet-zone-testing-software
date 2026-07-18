from __future__ import annotations

from catr_loss_calibrator.instrument_management.connection_service import InstrumentConnectionService
from catr_loss_calibrator.instrument_management.instrument_management_service import InstrumentManagementService
from catr_loss_calibrator.instrument_management.models import InstrumentConnectionConfig
from catr_loss_calibrator.instrument_management.recovery import ConnectionRecoveryPolicy
from catr_loss_calibrator.instrument_management.resource_lock import ResourceLock
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
