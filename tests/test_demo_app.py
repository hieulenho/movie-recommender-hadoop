import unittest
from unittest import mock


try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    AppTest = None


@unittest.skipIf(AppTest is None, "Streamlit is not installed.")
class DemoAppTests(unittest.TestCase):
    def run_app(self):
        app = AppTest.from_file("demo/app.py")
        app.run(timeout=15)
        return app

    def test_app_starts_without_exceptions(self) -> None:
        app = self.run_app()
        self.assertEqual(len(app.exception), 0)

    def test_main_title_exists(self) -> None:
        app = self.run_app()
        self.assertTrue(any("Movie Recommender Offline Demo" in item.value for item in app.title))

    def test_required_sections_exist(self) -> None:
        app = self.run_app()
        text = "\n".join([item.value for item in app.markdown] + [item.value for item in app.subheader])
        for label in ["Phim đã xem", "Gợi ý Top-K", "Pipeline đã triển khai"]:
            self.assertIn(label, text)

    def test_user_selector_and_user_101_recommendations_render(self) -> None:
        app = self.run_app()
        self.assertGreaterEqual(len(app.selectbox), 1)
        app.selectbox[0].set_value("101").run(timeout=15)
        text = "\n".join([item.value for item in app.markdown] + [item.value for item in app.subheader])
        self.assertIn("Gợi ý Top-K", text)

    def test_evaluation_metrics_and_fixture_warning_render(self) -> None:
        app = self.run_app()
        text = "\n".join(item.value for item in app.info)
        self.assertIn("Demonstration fixture", text)
        metric_labels = [item.label for item in app.metric]
        self.assertIn("RMSE", metric_labels)

    def test_missing_benchmark_guidance_rendered(self) -> None:
        app = self.run_app()
        code_text = "\n".join(item.value for item in app.code)
        self.assertIn("run_scalability_experiments_docker.ps1", code_text)

    def test_no_hadoop_or_subprocess_action_on_rerun(self) -> None:
        with mock.patch("subprocess.run", side_effect=AssertionError("subprocess.run must not be called")):
            with mock.patch("subprocess.Popen", side_effect=AssertionError("subprocess.Popen must not be called")):
                app = self.run_app()
                app.run(timeout=15)
                self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
