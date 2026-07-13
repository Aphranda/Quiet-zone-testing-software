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
            "SENS1:SWE:TIME?": "0.123",
            "CALC1:PAR:CAT:EXT?": '"Existing,S11"',
            "DISP:WIND1:CAT?": "1",
            "*OPC?": "1",
        }
        self.binary_values = [1.0, 0.0, 0.0, 1.0]
        self.fail_query: str | None = None
        self.system_errors: list[str] = []

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
        if command == "SYST:ERR?" and self.system_errors:
            return self.system_errors.pop(0)
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

    def test_query_sweep_time_reads_instrument_value(self) -> None:
        session = _Session()
        controller = _controller(session)

        self.assertEqual(controller.query_sweep_time_s(), 0.123)
        self.assertIn(("query", "SENS1:SWE:TIME?"), session.commands)

    def test_power_error_is_reported_without_being_cleared(self) -> None:
        session = _Session()
        session.system_errors = ['0,"No error"', '-222,"Data out of range"']
        controller = _controller(session)

        with self.assertRaises(ScpiCommunicationError):
            controller.configure_power(20.0)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("SOUR:POW 20", writes)
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

    def test_duplicate_display_trace_error_is_drained_after_parameter_switch(self) -> None:
        session = _Session()
        session.responses["CALC1:PAR:CAT:EXT?"] = '"CH1_SPARAM,S11"'
        session.system_errors = ['0,"No error"', '0,"No error"', '+110,"Duplicate trace number"', '0,"No error"']
        controller = _controller(session)

        controller.configure_measurement_parameter("S21")
        controller.configure_sweep(1.0e9, 2.0e9, 2)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("DISP:WIND1:TRAC1:DEL", writes)
        self.assertIn("DISP:WIND1:TRAC1:FEED 'CH1_SPARAM'", writes)

    def test_missing_display_trace_error_is_ignored_after_parameter_switch(self) -> None:
        session = _Session()
        session.responses["CALC1:PAR:CAT:EXT?"] = '"CH1_SPARAM,S21"'
        session.responses["DISP:WIND1:CAT?"] = ""
        session.system_errors = ['0,"No error"', '0,"No error"', '0,"No error"']
        controller = _controller(session)

        controller.configure_measurement_parameter("S11")
        controller.configure_sweep(1.0e9, 2.0e9, 2)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertNotIn("DISP:WIND1:TRAC1:DEL", writes)
        self.assertIn("DISP:WIND1:TRAC1:FEED 'CH1_SPARAM'", writes)

    def test_configure_continuous_sweep_writes_init_cont(self) -> None:
        session = _Session()
        controller = _controller(session)

        controller.configure_continuous_sweep(True)
        controller.configure_continuous_sweep(False)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("SENS1:SWE:MODE CONT", writes)
        self.assertIn("SENS1:SWE:MODE HOLD", writes)

    def test_stale_init_ignored_error_does_not_block_reconfiguration(self) -> None:
        session = _Session()
        session.system_errors = ['-213,"Init ignored"']
        controller = _controller(session)

        controller.configure_sweep(1.0e9, 2.0e9, 2)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("ABOR", writes)
        self.assertIn("SENS:FREQ:STAR 1000000000", writes)

    def test_pending_non_init_error_blocks_reconfiguration(self) -> None:
        session = _Session()
        session.system_errors = ['-222,"Data out of range"']
        controller = _controller(session)

        with self.assertRaises(ScpiCommunicationError):
            controller.configure_sweep(1.0e9, 2.0e9, 2)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("ABOR", writes)
        self.assertNotIn("SENS:FREQ:STAR 1000000000", writes)

    def test_measurement_uses_deterministic_single_trigger(self) -> None:
        session = _Session()
        controller = _controller(session)

        trace = controller.measure_s_parameter("S21")

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("TRIG:SOUR IMM", writes)
        self.assertIn("SENS1:SWE:MODE SING", writes)
        self.assertNotIn("INIT1:IMM", writes)
        self.assertEqual(trace.complex_values.size, 2)

    def test_measurement_does_not_rewrite_sing_when_already_single_trigger(self) -> None:
        session = _Session()
        session.responses["SENS1:SWE:MODE?"] = "SING"
        controller = _controller(session)

        controller.measure_s_parameter("S21")

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertNotIn("SENS1:SWE:MODE SING", writes)
        self.assertNotIn("INIT1:IMM", writes)

    def test_configuration_and_measurement_wait_for_operation_complete(self) -> None:
        session = _Session()
        controller = _controller(session)

        controller.configure_sweep(1.0e9, 2.0e9, 2)
        controller.measure_s_parameter("S21")

        commands = session.commands
        write_commands = [command for operation, command in commands if operation == "write"]
        self.assertIn("ABOR", write_commands)
        self.assertIn("SENS1:SWE:MODE SING", write_commands)

        sweep_stop_index = commands.index(("write", "SENS:FREQ:STOP 2000000000"))
        points_index = commands.index(("write", "SENS:SWE:POIN 2"))
        first_freq_read_index = commands.index(("query", "SENS:FREQ:STAR?"))
        self.assertIn(("query", "*OPC?"), commands[points_index:first_freq_read_index])
        self.assertGreater(first_freq_read_index, sweep_stop_index)

        trigger_index = commands.index(("write", "SENS1:SWE:MODE SING"))
        read_index = commands.index(("binary", "CALC:DATA? SDATA"))
        self.assertIn(("query", "*OPC?"), commands[trigger_index:read_index])

    def test_single_trigger_uses_sweep_mode_single_without_extra_init_trigger(self) -> None:
        session = _Session()
        controller = _controller(session)

        controller.measure_s_parameter("S21")
        controller.configure_sweep(1.0e9, 2.0e9, 2)

        writes = [command for operation, command in session.commands if operation == "write"]
        self.assertIn("SENS1:SWE:MODE SING", writes)
        self.assertNotIn("INIT1:IMM", writes)


if __name__ == "__main__":
    unittest.main()
