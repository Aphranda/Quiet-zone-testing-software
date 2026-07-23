from __future__ import annotations

from catr_loss_calibrator.hardware.scpi import ScpiCommunicationError, ScpiConnectionConfig, VisaScpiSession


class FakeResource:
    def __init__(self, *, write_failures: int = 0, query_failures: int = 0) -> None:
        self.timeout = 0
        self.read_termination = ""
        self.write_termination = ""
        self.write_failures = write_failures
        self.query_failures = query_failures
        self.commands: list[str] = []
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def write(self, command: str) -> None:
        self.commands.append(command)
        if self.write_failures > 0:
            self.write_failures -= 1
            raise OSError("temporary write failure")

    def query(self, command: str) -> str:
        self.commands.append(command)
        if self.query_failures > 0:
            self.query_failures -= 1
            raise OSError("query timeout")
        return "OK"


class FakeResourceManager:
    def __init__(self, resource: FakeResource, failures: set[str] | None = None) -> None:
        self.resource = resource
        self.failures = failures or set()
        self.opened: list[str] = []

    def open_resource(self, resource_name: str) -> FakeResource:
        self.opened.append(resource_name)
        if resource_name in self.failures:
            raise OSError("open failed")
        return self.resource


def test_visa_scpi_session_tries_socket_candidate_for_tcpip_instr_resource() -> None:
    resource = FakeResource()
    manager = FakeResourceManager(resource, failures={"TCPIP0::192.168.1.9::inst0::INSTR"})
    session = VisaScpiSession(
        ScpiConnectionConfig(resource_name="TCPIP0::192.168.1.9::inst0::INSTR"),
        resource_manager=manager,
    )

    session.open()

    assert manager.opened == [
        "TCPIP0::192.168.1.9::inst0::INSTR",
        "TCPIP0::192.168.1.9::5025::SOCKET",
    ]
    assert resource.timeout == 10_000
    assert resource.read_termination == "\n"
    assert resource.write_termination == "\n"


def test_visa_scpi_session_retries_write_failures() -> None:
    resource = FakeResource(write_failures=1)
    session = VisaScpiSession(
        ScpiConnectionConfig(resource_name="FAKE::VNA", retries=1, retry_delay_s=0),
        resource_manager=FakeResourceManager(resource),
    )
    session.open()

    session.write("SOUR:POW -7")

    assert resource.commands == ["SOUR:POW -7", "SOUR:POW -7"]


def test_visa_scpi_session_does_not_retry_queries() -> None:
    resource = FakeResource(query_failures=1)
    session = VisaScpiSession(
        ScpiConnectionConfig(resource_name="FAKE::VNA", retries=2, retry_delay_s=0),
        resource_manager=FakeResourceManager(resource),
    )
    session.open()

    try:
        session.query("*OPC?")
    except ScpiCommunicationError as exc:
        assert "SCPI query failed" in str(exc)
    else:
        raise AssertionError("Expected ScpiCommunicationError")
    assert resource.commands == ["*OPC?"]
