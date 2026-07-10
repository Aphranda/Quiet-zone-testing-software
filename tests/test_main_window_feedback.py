import unittest

from quiet_zone_tester.presentation.modules.app_feedback import MainWindowFeedback


class MainWindowFeedbackTest(unittest.TestCase):
    def test_info_updates_status_and_optional_log(self) -> None:
        statuses: list[str] = []
        infos: list[str] = []
        errors: list[str] = []

        feedback = MainWindowFeedback(statuses.append, infos.append, errors.append)

        feedback.info("就绪", "应用已启动。")
        feedback.info("处理中")

        self.assertEqual(statuses, ["就绪", "处理中"])
        self.assertEqual(infos, ["应用已启动。"])
        self.assertEqual(errors, [])

    def test_error_formats_message_logs_and_shows_dialog(self) -> None:
        statuses: list[str] = []
        infos: list[str] = []
        errors: list[str] = []
        dialogs: list[tuple[str, str]] = []
        feedback = MainWindowFeedback(
            statuses.append,
            infos.append,
            errors.append,
            show_error_dialog=lambda title, message: dialogs.append((title, message)),
            max_error_chars=5,
        )

        formatted = feedback.error("失败", "123456789")

        self.assertEqual(formatted, "12345...")
        self.assertEqual(statuses, ["失败"])
        self.assertEqual(infos, [])
        self.assertEqual(errors, ["失败: 12345..."])
        self.assertEqual(dialogs, [("失败", "12345...")])


if __name__ == "__main__":
    unittest.main()
