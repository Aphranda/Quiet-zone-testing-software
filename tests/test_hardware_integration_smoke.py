import os
import unittest


RUN_HARDWARE_INTEGRATION = os.environ.get("RUN_HARDWARE_INTEGRATION") == "1"


@unittest.skipUnless(RUN_HARDWARE_INTEGRATION, "Set RUN_HARDWARE_INTEGRATION=1 to run hardware smoke tests.")
class HardwareIntegrationSmokeTest(unittest.TestCase):
    def test_hardware_environment_is_explicitly_configured(self) -> None:
        required = [
            "HARDWARE_VNA_RESOURCE",
            "HARDWARE_POSITIONER_PORT",
            "HARDWARE_SWITCH_BOX_MODEL",
        ]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            self.skipTest("Missing hardware environment variables: " + ", ".join(missing))

        self.assertTrue(os.environ["HARDWARE_VNA_RESOURCE"].strip())
        self.assertTrue(os.environ["HARDWARE_POSITIONER_PORT"].strip())
        self.assertIn(os.environ["HARDWARE_SWITCH_BOX_MODEL"].strip().upper(), {"LCD74000F", "TC500"})


if __name__ == "__main__":
    unittest.main()
