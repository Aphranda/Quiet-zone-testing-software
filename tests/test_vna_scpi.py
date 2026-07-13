import unittest

from pyvisa import VisaIOError

from quiet_zone_tester.hardware.transport.visa_scpi import (
    ScpiCommunicationError,
    ScpiConnectionConfig,
    VisaScpiSession,
)
from quiet_zone_tester.hardware.vna.scpi import ScpiVnaController, VnaScpiConfig


class _Session:
    def __init__(self) -> None:
        self.is_open = False
        self.commands: list[tuple[str, str]] = []
        self.responses: dict[str, str] = {
            "*IDN?": "Keysight Technologies,E5080B,MY123,1.0",
            "SYST:ERR?": '0,"No error"',
            "SENS:FREQ:STAR?": "1000000000",
            "SENS:FREQ:STOP?": "2000000000",
            "SENS:SWE:POIN?": "2",
            "CALC1:PAR:CAT:EXT?": '"Existing,S11"',
            "*OPC?": "1",
        }
        self.binary_values = [1.0, 0.0, 0.0, 1.0]
        self.fail_query: str | None = None

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, command: str) -> None:
        self.commands.append(("write", command))

    def query(self, command: str) -> str:
        self.commands.append(("query", command))
        if command == self.fail_query:
            raise ScpiCommunicationError("query failed")
        return self.responses.get(command, "")

    def query_binary_values(self, command: str, datatype: str, is_big_endian: bool) -> list[float]:
        self.commands.append(("binary", command))
        return self.binary_values


def _controller(session: _Session) -> ScpiVnaController:
    controller = ScpiVnaController(VnaScpiConfig("TCPIP0::HOST::inst0::INSTR", expected_model="E5080B"))
    controller._session = session
    controller.connect()
    controller._points = 2
    return controller


class _FailingQueryResource:
    def __init__(self) -> None:
        self.query_count = 0

    def query(self, command: str) -> str:
        self.query_count += 1
        raise VisaIOError(-1073807339)


class ScpiVnaControllerTest(unittest.TestCase):
    def test_query_is_not_retried_after_timeout(self) -> None:
        resource = _FailingQueryResource()
        session = VisaScpiSession(ScpiConnectionConfig("TEST", retries=3))
        session._resource = resource

        with self.assertRaises(ScpiCommunicationError):
            session.query("*IDN?")

        self.assertEqual(resource.query_count, 1)

    def test_connect_closes_session_when_identification_fails(self) -> None:
        session = _Session()
        session.fail_query = "*IDN?"
        controller = ScpiVnaController(VnaScpiConfig("TCPIP0::HOST::inst0::INSTR"))
        controller._session = session

        with self.assertRaises(ScpiCommunicationError):
            controller.connect()

        self.assertFalse(session.is_open)

    def test_configure_sweep_checks_errors_and_reads_actual_values(self) -> None:
        session = _Session()
        controller = _controller(session)

        controller.configure_sweep(1.0e9, 2.0e9, 2)

        self.assertIn(("query", "SYST:ERR?"), session.commands)
        self.assertIn(("query", "SENS:FREQ:STAR?"), session.commands)
        self.assertIn(("query", "SENS:SWE:POIN?"), session.commands)

    def test_power_error_is_reported_without_being_cleared(self) -> None:
        session = _Session()
        session.responses["SYST:ERR?"] = '-222,"Data out of range"'
        controller = _controller(session)

        with self.assertRaises(ScpiCommunicationError):
            controller.configure_power(20.0)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertNotIn("*CLS", writes)

    def test_e5080b_parameter_is_recreated_deterministically(self) -> None:
        session = _Session()
        session.responses["CALC1:PAR:CAT:EXT?"] = '"CH1_SPARAM,S11,Other,S21"'
        controller = _controller(session)

        controller.configure_measurement_parameter("S21")

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("CALC1:PAR:DEL 'CH1_SPARAM'", writes)
        self.assertIn("CALC1:PAR:DEF:EXT 'CH1_SPARAM','S21'", writes)
        self.assertIn("CALC1:PAR:SEL 'CH1_SPARAM'", writes)

    def test_measurement_uses_deterministic_single_trigger(self) -> None:
        session = _Session()
        controller = _controller(session)

        trace = controller.measure_s_parameter("S21")

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("INIT1:CONT OFF", writes)
        self.assertIn("TRIG:SOUR IMM", writes)
        self.assertIn("INIT1:IMM", writes)
        self.assertEqual(trace.complex_values.size, 2)


if __name__ == "__main__":
    unittest.main()
