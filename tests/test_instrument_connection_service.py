import unittest

from quiet_zone_tester.domains.instrument_management import (
    InstrumentConnectionService,
    InstrumentConnectionServiceError,
)
from quiet_zone_tester.hardware import InstrumentInfo


class _Controller:
    def __init__(self, connected: bool = False, fail_disconnect: bool = False) -> None:
        self._connected = connected
        self.fail_disconnect = fail_disconnect
        self.calls: list[str] = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> InstrumentInfo:
        self.calls.append("connect")
        self._connected = True
        return InstrumentInfo("RESOURCE", "MODEL", "SERIAL")

    def disconnect(self) -> None:
        self.calls.append("disconnect")
        if self.fail_disconnect:
            raise RuntimeError("disconnect failed")
        self._connected = False


class InstrumentConnectionServiceTest(unittest.TestCase):
    def test_connect_controller_disconnects_existing_connection_first(self) -> None:
        controller = _Controller(connected=True)

        info = InstrumentConnectionService().connect_controller(controller, "VNA")

        self.assertEqual(info.model, "MODEL")
        self.assertEqual(controller.calls, ["disconnect", "connect"])

    def test_disconnect_all_collects_errors(self) -> None:
        ok = _Controller(connected=True)
        failed = _Controller(connected=True, fail_disconnect=True)

        with self.assertLogs("quiet_zone_tester.domains.instrument_management.connection_service", level="ERROR"):
            with self.assertRaises(InstrumentConnectionServiceError):
                InstrumentConnectionService().disconnect_all([ok, failed])

        self.assertEqual(ok.calls, ["disconnect"])
        self.assertEqual(failed.calls, ["disconnect"])

    def test_cleanup_after_failed_connect_swallows_disconnect_errors(self) -> None:
        failed = _Controller(connected=True, fail_disconnect=True)

        with self.assertLogs("quiet_zone_tester.domains.instrument_management.connection_service", level="ERROR"):
            InstrumentConnectionService().cleanup_after_failed_connect([failed])

        self.assertEqual(failed.calls, ["disconnect"])

    def test_disconnect_controller_ignores_missing_controller(self) -> None:
        InstrumentConnectionService().disconnect_controller(None, "missing")

    def test_connect_controller_rejects_missing_controller(self) -> None:
        with self.assertRaises(InstrumentConnectionServiceError):
            InstrumentConnectionService().connect_controller(None, "missing")


if __name__ == "__main__":
    unittest.main()
