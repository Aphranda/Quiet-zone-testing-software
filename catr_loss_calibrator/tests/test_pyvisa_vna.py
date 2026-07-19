from __future__ import annotations

import numpy as np

from catr_loss_calibrator.hardware.vna.pyvisa_vna import PyVisaVna


class FakeVisaResource:
    def __init__(self, values: dict[str, list[float] | Exception]) -> None:
        self.values = values
        self.commands: list[str] = []

    def write(self, command: str) -> None:
        self.commands.append(command)

    def query(self, command: str) -> str:
        self.commands.append(command)
        upper = command.strip().upper()
        if upper == "*OPC?":
            return "1"
        if upper == "SYST:ERR?":
            return "0,No error"
        value = self.values.get(command)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return ""
        return ",".join(str(item) for item in value)

    def query_ascii_values(self, command: str):
        self.commands.append(command)
        value = self.values.get(command)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return []
        return value


def connected_vna(resource: FakeVisaResource) -> PyVisaVna:
    vna = PyVisaVna("FAKE::VNA")
    vna._resource = resource
    vna._connected = True
    vna._selected_parameter = "S21"
    vna._points = 3
    return vna


def test_pyvisa_vna_reads_formatted_trace_data() -> None:
    resource = FakeVisaResource(
        {
            "SENS:FREQ:DATA?": [1.0, 2.0, 3.0],
            "CALC:DATA? FDATA": [-1.0, -2.0, -3.0],
        }
    )
    trace = connected_vna(resource).read_s_parameter("S21")

    assert np.allclose(trace.frequency_hz, np.array([1.0, 2.0, 3.0]))
    assert np.allclose(trace.value_db, np.array([-1.0, -2.0, -3.0]))
    assert np.allclose(trace.phase_deg, np.zeros(3))


def test_pyvisa_vna_prefers_sdata_over_formatted_trace_data() -> None:
    resource = FakeVisaResource(
        {
            "SENS:FREQ:DATA?": [1.0, 2.0],
            "CALC:DATA? SDATA": [1.0, 0.0, 0.0, 1.0],
            "CALC:DATA? FDATA": [-10.0, -20.0],
        }
    )
    vna = connected_vna(resource)
    vna._points = 2
    trace = vna.read_s_parameter("S21")

    assert np.allclose(trace.value_db, np.array([0.0, 0.0]))
    assert "CALC:DATA? SDATA" in resource.commands
    assert "CALC:DATA? FDATA" not in resource.commands


def test_pyvisa_vna_falls_back_to_sdata_complex_values() -> None:
    resource = FakeVisaResource(
        {
            "SENS:FREQ:DATA?": [1.0, 2.0],
            "CALC:DATA? FDATA": RuntimeError("unsupported"),
            "CALC:DATA? SDATA": [1.0, 0.0, 0.0, 1.0],
        }
    )
    vna = connected_vna(resource)
    vna._points = 2
    trace = vna.read_s_parameter("S21")

    assert np.allclose(trace.value_db, np.array([0.0, 0.0]))
    assert np.allclose(trace.phase_deg, np.array([0.0, 90.0]))


def test_pyvisa_vna_uses_stable_source_power_command() -> None:
    resource = FakeVisaResource({})
    vna = connected_vna(resource)
    vna.model = "N5245B"

    vna.configure_power(-7.0)

    assert "SOUR:POW -7" in resource.commands
    assert "SOUR1:POW1:LEV:IMM:AMPL -7" not in resource.commands


def test_pyvisa_vna_trigger_uses_stable_sweep_mode_single_flow() -> None:
    resource = FakeVisaResource({})
    vna = connected_vna(resource)

    vna.trigger_sweep("S21")

    assert "TRIG:SOUR IMM" in resource.commands
    assert "SENS1:SWE:MODE SING" in resource.commands
    assert "INIT1:CONT OFF" not in resource.commands
    assert "INIT1:IMM" not in resource.commands


def test_pyvisa_vna_configure_sweep_reads_actual_instrument_values() -> None:
    resource = FakeVisaResource(
        {
            "SENS:FREQ:STAR?": [1.1e9],
            "SENS:FREQ:STOP?": [2.2e9],
            "SENS:SWE:POIN?": [11],
        }
    )
    vna = connected_vna(resource)

    vna.configure_sweep(1.0e9, 2.0e9, 21)

    assert vna._start_hz == 1.1e9
    assert vna._stop_hz == 2.2e9
    assert vna._points == 11
