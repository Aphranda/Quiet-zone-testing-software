import unittest

from quiet_zone_tester.domains.scan_management import (
    ScanState,
    ScanStateError,
    ScanStateMachine,
)


class ScanStateMachineTest(unittest.TestCase):
    def test_accepts_nominal_flow(self) -> None:
        machine = ScanStateMachine()

        self.assertEqual(machine.state, ScanState.IDLE)
        self.assertTrue(machine.can_start)

        self.assertEqual(machine.handle("start_scan"), ScanState.PLANNING)
        self.assertEqual(machine.handle("plan_ready"), ScanState.RUNNING)
        self.assertTrue(machine.can_pause)

        self.assertEqual(machine.handle("pause"), ScanState.PAUSED)
        self.assertTrue(machine.can_resume)

        self.assertEqual(machine.handle("resume"), ScanState.RUNNING)
        self.assertEqual(machine.handle("stop"), ScanState.STOPPING)
        self.assertEqual(machine.handle("stopped"), ScanState.COMPLETED)
        self.assertEqual(machine.handle("reset"), ScanState.IDLE)

    def test_rejects_illegal_transition(self) -> None:
        machine = ScanStateMachine()

        with self.assertRaises(ScanStateError):
            machine.handle("pause")

        self.assertEqual(machine.state, ScanState.IDLE)


if __name__ == "__main__":
    unittest.main()
