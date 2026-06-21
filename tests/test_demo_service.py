import tempfile
import unittest
from pathlib import Path

from demo.data_loader import build_demo_bundle, build_sample_bundle
from demo.models import DemoDataBundle, DemoValidationError, Recommendation, UserProfile, WatchedMovie
from demo.service import (
    build_history_rows,
    build_recommendation_csv,
    build_recommendation_rows,
    build_user_summary,
    get_user_profile,
    list_user_ids,
    summarize_benchmark_results,
    summarize_evaluation_metrics,
    validate_bundle_integrity,
)


class DemoServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = build_sample_bundle()
        self.profile = get_user_profile(self.bundle, 101)

    def test_numerically_sorted_user_ids(self) -> None:
        self.assertEqual(list_user_ids(self.bundle), [101, 102, 103, 104])

    def test_correct_watched_count(self) -> None:
        self.assertEqual(build_user_summary(self.profile)["watched_movie_count"], 2)

    def test_correct_recommendation_count(self) -> None:
        self.assertEqual(build_user_summary(self.profile)["recommendation_count"], 2)

    def test_correct_historical_rating_average(self) -> None:
        self.assertEqual(build_user_summary(self.profile)["average_historical_rating"], 4.0)

    def test_correct_recommendation_score_average(self) -> None:
        self.assertAlmostEqual(build_user_summary(self.profile)["average_recommendation_score"], 3.4)

    def test_correct_highest_recommendation_score(self) -> None:
        self.assertEqual(build_user_summary(self.profile)["highest_recommendation_score"], 3.8)

    def test_correct_metadata_enrichment(self) -> None:
        rows = build_recommendation_rows(self.profile, self.bundle.metadata)
        self.assertEqual(rows[0]["Title"], "Demo Movie 3")

    def test_correct_metadata_fallback(self) -> None:
        rows = build_history_rows(self.profile, {})
        self.assertEqual(rows[0]["Title"], "Movie 1")

    def test_correct_recommendation_csv_header(self) -> None:
        csv_text = build_recommendation_csv(self.profile, self.bundle.metadata)
        self.assertEqual(csv_text.splitlines()[0], "rank,movieId,title,year,genres,predictedScore")

    def test_correct_selected_user_csv_rows(self) -> None:
        csv_text = build_recommendation_csv(self.profile, self.bundle.metadata)
        self.assertIn("1,3,Demo Movie 3,,,3.8000000000", csv_text)
        self.assertNotIn("102,", csv_text)

    def test_detect_watched_recommendations(self) -> None:
        bundle = DemoDataBundle(
            users={
                1: UserProfile(
                    1,
                    (WatchedMovie(1, 5),),
                    (Recommendation(1, 1, 4.0, "4.0000000000"),),
                )
            },
            metadata={},
        )
        self.assertTrue(validate_bundle_integrity(bundle))

    def test_detect_recommendations_for_unknown_users(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = root / "history.txt"
            recs = root / "recs.txt"
            history.write_text("1\t1:5\n", encoding="utf-8")
            recs.write_text("2\t3:4.0\n", encoding="utf-8")
            with self.assertRaisesRegex(DemoValidationError, "unknown user"):
                build_demo_bundle(history, recs)

    def test_return_recommendations_in_offline_rank_order(self) -> None:
        self.assertEqual([row["Movie ID"] for row in build_recommendation_rows(self.profile, self.bundle.metadata)], [3, 4])

    def test_detailed_recommendation_scores_keep_ten_decimal_places(self) -> None:
        rows = build_recommendation_rows(self.profile, self.bundle.metadata)
        self.assertEqual(rows[0]["Predicted score"], "3.8000000000")

    def test_handle_missing_optional_evaluation_data(self) -> None:
        bundle = DemoDataBundle(users=self.bundle.users, metadata=self.bundle.metadata)
        self.assertEqual(summarize_evaluation_metrics(bundle.evaluation), {})

    def test_handle_missing_optional_benchmark_data(self) -> None:
        self.assertEqual(summarize_benchmark_results(tuple())["successful_count"], 0)


if __name__ == "__main__":
    unittest.main()

