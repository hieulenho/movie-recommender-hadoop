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

    def run_local_app(self):
        app = self.run_app()
        app.selectbox[0].set_value("Local pipeline artifacts").run(timeout=30)
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

    def test_local_full_reference_defaults_are_repository_relative(self) -> None:
        app = self.run_local_app()
        values = [item.value for item in app.text_input]
        self.assertIn("results/full-reference-dataset/cosine/user-history", values)
        self.assertIn("results/full-reference-dataset/cosine/recommendations", values)
        self.assertIn("results/full-reference-dataset/cosine/metrics.json", values)
        self.assertTrue(all("D:\\" not in value for value in values))

    def test_empty_optional_metadata_and_benchmark_paths_are_accepted(self) -> None:
        app = self.run_local_app()
        app.text_input[3].set_value("")
        app.text_input[4].set_value("")
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Chưa có benchmark CSV thực" in item.value for item in app.warning))

    def test_missing_required_user_history_path_produces_concise_error(self) -> None:
        app = self.run_local_app()
        app.text_input[0].set_value("missing/user-history")
        app.run(timeout=15)
        error_text = "\n".join(item.value for item in app.error)
        self.assertIn("Thiếu artifact bắt buộc: Lịch sử người dùng", error_text)
        self.assertIn("results/full-reference-dataset/cosine/user-history", error_text)
        self.assertNotIn("Traceback", error_text)

    def test_missing_required_recommendation_path_produces_concise_error(self) -> None:
        app = self.run_local_app()
        app.text_input[1].set_value("missing/recommendations")
        app.run(timeout=15)
        error_text = "\n".join(item.value for item in app.error)
        self.assertIn("Thiếu artifact bắt buộc: Gợi ý Top-K cuối cùng", error_text)
        self.assertIn("results/full-reference-dataset/cosine/recommendations", error_text)

    def test_compact_metric_formatting_uses_three_decimal_places(self) -> None:
        app = self.run_app()
        values_by_label = {item.label: item.value for item in app.metric}
        self.assertEqual(values_by_label["Rating TB"], "4.000")
        self.assertEqual(values_by_label["Score TB"], "3.400")
        self.assertEqual(values_by_label["Score cao nhất"], "3.800")

    def test_all_four_tabs_render(self) -> None:
        app = self.run_app()
        tab_labels = [item.label for item in app.tabs]
        self.assertEqual(
            tab_labels,
            ["Gợi ý cho người dùng", "Đánh giá mô hình", "Khả năng mở rộng", "Kiến trúc hệ thống"],
        )


if __name__ == "__main__":
    unittest.main()
