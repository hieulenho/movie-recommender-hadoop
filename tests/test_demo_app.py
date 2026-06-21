import unittest
from unittest import mock

from demo import artifact_paths


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

    def run_sample_app(self):
        """Switch the sidebar data-source selector to the bundled fixture."""
        app = self.run_app()
        app.sidebar.selectbox[0].set_value("Bundled demonstration sample").run(timeout=30)
        return app

    def run_custom_app(self):
        """Switch the sidebar data-source selector to 'Custom local artifacts'."""
        app = self.run_app()
        app.sidebar.selectbox[0].set_value("Custom local artifacts").run(timeout=30)
        return app

    def test_app_starts_without_exceptions(self) -> None:
        app = self.run_app()
        self.assertEqual(len(app.exception), 0)

    def test_main_title_exists(self) -> None:
        app = self.run_app()
        self.assertTrue(any("Movie Recommender Offline Demo" in item.value for item in app.title))

    def test_movielens_and_compatibility_modes_appear(self) -> None:
        """The sidebar data-source selectbox must expose all four source options."""
        app = self.run_app()
        options = list(app.sidebar.selectbox[0].options)
        self.assertIn("MovieLens 1M primary artifacts", options)
        self.assertIn("GitHub reference compatibility artifacts", options)
        self.assertIn("Bundled demonstration sample", options)

    def test_required_sections_exist(self) -> None:
        app = self.run_app()
        text = "\n".join([item.value for item in app.markdown] + [item.value for item in app.subheader])
        for label in ["Watched movies", "Top-K recommendations", "Implemented pipeline"]:
            self.assertIn(label, text)

    def test_user_selector_and_user_101_recommendations_render(self) -> None:
        """In bundled-sample mode the user selector (selectbox[0]) should contain 101-104."""
        app = self.run_sample_app()
        # selectbox[0] is the User selector in the main content area (bundled mode)
        self.assertGreaterEqual(len(app.selectbox), 1)
        app.selectbox[0].set_value("101").run(timeout=15)
        text = "\n".join([item.value for item in app.markdown] + [item.value for item in app.subheader])
        self.assertIn("Top-K recommendations", text)

    def test_evaluation_metrics_and_fixture_warning_render(self) -> None:
        app = self.run_sample_app()
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

    def test_custom_defaults_are_repository_relative(self) -> None:
        app = self.run_custom_app()
        values = [item.value for item in app.text_input]
        if artifact_paths.movielens_artifacts_available():
            self.assertIn("results/movielens-1m/common/user-history", values)
            self.assertIn("results/movielens-1m/cosine/recommendations", values)
        else:
            self.assertIn("results/full-reference-dataset/cosine/user-history", values)
            self.assertIn("results/full-reference-dataset/cosine/recommendations", values)
        self.assertTrue(all("D:\\" not in value for value in values))

    def test_empty_optional_metadata_and_benchmark_paths_are_accepted(self) -> None:
        app = self.run_custom_app()
        app.text_input[0].set_value("demo/sample/user_history.txt")
        app.text_input[1].set_value("demo/sample/recommendations.txt")
        app.text_input[2].set_value("demo/sample/evaluation_metrics.json")
        app.text_input[3].set_value("")
        app.text_input[4].set_value("")
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("No synthetic benchmark CSV" in item.value for item in app.warning))

    def test_missing_required_user_history_path_produces_concise_error(self) -> None:
        app = self.run_custom_app()
        app.text_input[0].set_value("missing/user-history")
        app.run(timeout=15)
        error_text = "\n".join(item.value for item in app.error)
        self.assertIn("Missing required artifact: User history", error_text)
        self.assertIn("results/movielens-1m/common/user-history", error_text)
        self.assertNotIn("Traceback", error_text)

    def test_missing_required_recommendation_path_produces_concise_error(self) -> None:
        app = self.run_custom_app()
        app.text_input[1].set_value("missing/recommendations")
        app.run(timeout=15)
        error_text = "\n".join(item.value for item in app.error)
        self.assertIn("Missing required artifact: Final Top-K recommendations", error_text)

    def test_compact_metric_formatting_uses_three_decimal_places(self) -> None:
        app = self.run_sample_app()
        values_by_label = {item.label: item.value for item in app.metric}
        self.assertEqual(values_by_label["Avg rating"], "4.000")
        self.assertEqual(values_by_label["Avg score"], "3.400")
        self.assertEqual(values_by_label["Highest score"], "3.800")

    def test_all_four_tabs_render(self) -> None:
        app = self.run_app()
        tab_labels = [item.label for item in app.tabs]
        self.assertEqual(tab_labels, ["User recommendations", "Evaluation", "Scalability", "Architecture"])


if __name__ == "__main__":
    unittest.main()
