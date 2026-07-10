import unittest

import quiet_zone_tester.main as entrypoint


class ApplicationEntrypointTest(unittest.TestCase):
    def test_Main_is_canonical_entrypoint_and_main_remains_compatible(self) -> None:
        original_run_app = entrypoint.run_app
        calls: list[str] = []
        try:
            entrypoint.run_app = lambda: calls.append("run_app") or 42

            self.assertEqual(entrypoint.Main(), 42)
            self.assertEqual(entrypoint.main(), 42)
        finally:
            entrypoint.run_app = original_run_app

        self.assertEqual(calls, ["run_app", "run_app"])


if __name__ == "__main__":
    unittest.main()
