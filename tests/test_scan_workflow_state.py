import unittest

from quiet_zone_tester.application import ScanWorkflowState


class ScanWorkflowStateTest(unittest.TestCase):
    def test_begin_scan_resets_runtime_flags(self) -> None:
        state = ScanWorkflowState(stop_requested=True, paused=True, failed=True, completed_points=5)

        state.begin_scan(12)

        self.assertTrue(state.sampling_active)
        self.assertEqual(state.active_mode, "scan")
        self.assertEqual(state.completed_points, 0)
        self.assertEqual(state.total_points, 12)
        self.assertFalse(state.stop_requested)
        self.assertFalse(state.paused)
        self.assertFalse(state.failed)

    def test_pause_resume_stop_and_failure_transitions(self) -> None:
        state = ScanWorkflowState()
        state.begin_scan(10)

        state.pause()
        self.assertTrue(state.paused)

        state.resume()
        self.assertFalse(state.paused)

        state.request_stop()
        self.assertTrue(state.stop_requested)
        self.assertFalse(state.sampling_active)
        self.assertIsNone(state.active_mode)

        state.begin_scan(10)
        state.mark_failed()
        self.assertTrue(state.failed)
        self.assertFalse(state.sampling_active)

    def test_finished_cleanup_returns_snapshot_and_resets_flags(self) -> None:
        state = ScanWorkflowState(sampling_active=True, task_running=True, paused=True, stop_requested=True)

        stop_requested, failed = state.begin_finished_cleanup()

        self.assertTrue(stop_requested)
        self.assertFalse(failed)
        self.assertFalse(state.task_running)
        self.assertFalse(state.paused)

        state.finish_inactive_cleanup()
        self.assertFalse(state.stop_requested)
        self.assertFalse(state.failed)

    def test_busy_helpers_include_scan_and_stop_tasks(self) -> None:
        state = ScanWorkflowState()
        self.assertFalse(state.connection_busy(False))
        self.assertFalse(state.test_busy(False))

        state.begin_scan(1)
        self.assertTrue(state.connection_busy(False))
        self.assertTrue(state.test_busy(False))

        state.reset()
        state.set_stop_positioner_task_running(True)
        self.assertTrue(state.connection_busy(False))
        self.assertFalse(state.test_busy(False))


if __name__ == "__main__":
    unittest.main()
