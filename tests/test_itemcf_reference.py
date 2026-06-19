import argparse
import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.itemcf_reference import (
    ItemCFError,
    NEIGHBORS_HEADER,
    RECOMMENDATIONS_HEADER,
    Recommendation,
    SimilarityEntry,
    build_arg_parser,
    build_statistics,
    build_user_histories,
    compute_directed_similarities,
    compute_pair_statistics,
    generate_top_k_recommendations,
    load_normalized_ratings,
    parse_positive_int,
    retain_top_l_neighbors,
    run_reference_pipeline,
    score_unseen_candidates,
    validate_positive_parameters,
    write_neighbor_csv,
    write_recommendation_csv,
)


FIXTURE = Path("tests/fixtures/itemcf/ratings.csv")


class ItemCFReferenceTests(unittest.TestCase):
    def write_csv(self, root: Path, content: str) -> Path:
        path = root / "ratings.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def load_fixture(self):
        result = load_normalized_ratings(FIXTURE)
        histories = build_user_histories(result.records)
        pair_stats = compute_pair_statistics(histories)
        return result, histories, pair_stats

    def find_entry(
        self,
        similarities: dict[int, list[SimilarityEntry]],
        source: int,
        neighbor: int,
    ) -> SimilarityEntry:
        for entry in similarities.get(source, []):
            if entry.neighbor_movie_id == neighbor:
                return entry
        self.fail(f"Missing similarity entry {source}->{neighbor}")

    def test_load_valid_normalized_csv(self) -> None:
        result = load_normalized_ratings(FIXTURE)
        self.assertEqual(result.input_rows, 13)
        self.assertEqual(result.accepted_ratings, 12)
        self.assertEqual(result.exact_duplicate_rows_ignored, 1)

    def test_reject_incorrect_csv_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "user,movie,rating,date\n1,1,5,2005-01-01\n")
            with self.assertRaisesRegex(ItemCFError, "header"):
                load_normalized_ratings(path)

    def test_reject_empty_dataset_after_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n")
            with self.assertRaisesRegex(ItemCFError, "no rating rows"):
                load_normalized_ratings(path)

    def test_reject_invalid_user_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n0,1,5,2005-01-01\n")
            with self.assertRaisesRegex(ItemCFError, "userId"):
                load_normalized_ratings(path)

    def test_reject_invalid_movie_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n1,0,5,2005-01-01\n")
            with self.assertRaisesRegex(ItemCFError, "movieId"):
                load_normalized_ratings(path)

    def test_reject_rating_outside_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n1,1,6,2005-01-01\n")
            with self.assertRaisesRegex(ItemCFError, "rating"):
                load_normalized_ratings(path)

    def test_reject_non_integer_rating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n1,1,five,2005-01-01\n")
            with self.assertRaisesRegex(ItemCFError, "rating"):
                load_normalized_ratings(path)

    def test_reject_invalid_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(Path(tmp), "userId,movieId,rating,date\n1,1,5,2005-02-30\n")
            with self.assertRaisesRegex(ItemCFError, "date"):
                load_normalized_ratings(path)

    def test_ignore_exact_duplicate_row(self) -> None:
        result = load_normalized_ratings(FIXTURE)
        self.assertEqual(result.exact_duplicate_rows_ignored, 1)
        self.assertEqual(len([record for record in result.records if record[:2] == (101, 1)]), 1)

    def test_reject_conflicting_duplicate_user_movie_ratings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(
                Path(tmp),
                "userId,movieId,rating,date\n1,1,5,2005-01-01\n1,1,4,2005-01-01\n",
            )
            with self.assertRaisesRegex(ItemCFError, "conflicting duplicate"):
                load_normalized_ratings(path)

    def test_build_correct_user_histories(self) -> None:
        _result, histories, _pair_stats = self.load_fixture()
        self.assertEqual(histories[101], {1: 5, 2: 4, 3: 1})
        self.assertEqual(len(histories), 4)

    def test_create_unordered_pairs_only_once_per_user(self) -> None:
        histories = {1: {1: 5, 2: 4, 3: 1}}
        pair_stats = compute_pair_statistics(histories)
        self.assertEqual(sorted(pair_stats), [(1, 2), (1, 3), (2, 3)])

    def test_not_create_self_pairs(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        self.assertFalse(any(left == right for left, right in pair_stats))

    def test_compute_common_users_correctly(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        self.assertEqual(pair_stats[(1, 2)].common_users, 2)

    def test_compute_sum_xy_correctly(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        self.assertEqual(pair_stats[(1, 2)].sum_xy, 36)

    def test_compute_sum_x2_and_sum_y2_correctly(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        self.assertEqual(pair_stats[(1, 2)].sum_x2, 41)
        self.assertEqual(pair_stats[(1, 2)].sum_y2, 32)

    def test_filter_by_min_common_users(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        similarities, eligible_count = compute_directed_similarities(pair_stats, "cosine", 3)
        self.assertEqual(eligible_count, 0)
        self.assertEqual(similarities, {})

    def test_compute_row_normalized_cooccurrence_correctly(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        similarities, _eligible_count = compute_directed_similarities(
            pair_stats,
            "cooccurrence",
            1,
        )
        entry = self.find_entry(similarities, 1, 2)
        self.assertTrue(math.isclose(entry.similarity, 1 / 3))

    def test_compute_cosine_similarity_correctly(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        similarities, _eligible_count = compute_directed_similarities(pair_stats, "cosine", 1)
        entry = self.find_entry(similarities, 1, 4)
        self.assertTrue(math.isclose(entry.similarity, 40 / 41))

    def test_produce_both_directed_similarity_relations(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        similarities, _eligible_count = compute_directed_similarities(pair_stats, "cosine", 1)
        left = self.find_entry(similarities, 1, 4)
        right = self.find_entry(similarities, 4, 1)
        self.assertTrue(math.isclose(left.similarity, right.similarity))

    def test_keep_at_most_top_l_neighbors(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        similarities, _eligible_count = compute_directed_similarities(pair_stats, "cooccurrence", 1)
        retained = retain_top_l_neighbors(similarities, 2)
        self.assertTrue(all(len(entries) <= 2 for entries in retained.values()))

    def test_break_neighbor_ties_by_movie_id_ascending(self) -> None:
        _result, _histories, pair_stats = self.load_fixture()
        similarities, _eligible_count = compute_directed_similarities(pair_stats, "cooccurrence", 1)
        retained = retain_top_l_neighbors(similarities, 2)
        self.assertEqual([entry.neighbor_movie_id for entry in retained[1]], [2, 3])

    def test_exclude_already_watched_movies(self) -> None:
        _result, histories, pair_stats = self.load_fixture()
        similarities, _eligible_count = compute_directed_similarities(pair_stats, "cooccurrence", 1)
        retained = retain_top_l_neighbors(similarities, 50)
        recommendations = generate_top_k_recommendations(histories, retained, 10)
        user_101_movies = [item.movie_id for item in recommendations if item.user_id == 101]
        self.assertEqual(user_101_movies, [4])

    def test_combine_contributions_from_multiple_rated_items(self) -> None:
        _result, histories, pair_stats = self.load_fixture()
        similarities, _eligible_count = compute_directed_similarities(pair_stats, "cooccurrence", 1)
        retained = retain_top_l_neighbors(similarities, 50)
        scores = score_unseen_candidates(histories[101], retained)
        self.assertTrue(math.isclose(scores[4], (5 + 4 + 1) / 3))

    def test_apply_weighted_average_score_normalization(self) -> None:
        histories = {1: {1: 5, 2: 1}}
        retained = {
            1: [SimilarityEntry(1, 4, 0.5, 1)],
            2: [SimilarityEntry(2, 4, 1.5, 1)],
        }
        scores = score_unseen_candidates(histories[1], retained)
        self.assertTrue(math.isclose(scores[4], 2.0))

    def test_keep_at_most_top_k_recommendations(self) -> None:
        histories = {1: {1: 5}}
        retained = {1: [SimilarityEntry(1, 2, 1.0, 1), SimilarityEntry(1, 3, 0.9, 1)]}
        recommendations = generate_top_k_recommendations(histories, retained, 1)
        self.assertEqual(len(recommendations), 1)

    def test_break_recommendation_ties_by_movie_id_ascending(self) -> None:
        histories = {1: {1: 5}}
        retained = {1: [SimilarityEntry(1, 3, 1.0, 1), SimilarityEntry(1, 2, 1.0, 1)]}
        recommendations = generate_top_k_recommendations(histories, retained, 10)
        self.assertEqual([item.movie_id for item in recommendations], [2, 3])

    def test_assign_ranks_starting_from_one(self) -> None:
        histories = {1: {1: 5}}
        retained = {1: [SimilarityEntry(1, 2, 1.0, 1), SimilarityEntry(1, 3, 0.9, 1)]}
        recommendations = generate_top_k_recommendations(histories, retained, 10)
        self.assertEqual([item.rank for item in recommendations], [1, 2])

    def test_produce_exact_neighbor_csv_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "neighbors.csv"
            write_neighbor_csv({1: [SimilarityEntry(1, 2, 0.5, 3)]}, output)
            with output.open("r", encoding="utf-8", newline="") as csv_file:
                self.assertEqual(next(csv.reader(csv_file)), NEIGHBORS_HEADER)

    def test_produce_exact_recommendation_csv_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "recommendations.csv"
            write_recommendation_csv([Recommendation(1, 1, 2, 4.5)], output)
            with output.open("r", encoding="utf-8", newline="") as csv_file:
                self.assertEqual(next(csv.reader(csv_file)), RECOMMENDATIONS_HEADER)

    def test_produce_internally_consistent_statistics_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stats = run_reference_pipeline(
                FIXTURE,
                "cosine",
                root / "out" / "neighbors.csv",
                root / "out" / "recommendations.csv",
                root / "out" / "stats.json",
                min_common_users=1,
                top_l=50,
                top_k=10,
            )
            saved = json.loads((root / "out" / "stats.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, stats)
            self.assertEqual(stats["directed_similarity_entries_before_top_l"], 12)
            self.assertEqual(stats["directed_similarity_entries_after_top_l"], 12)
            self.assertEqual(stats["recommendation_rows"], 4)

    def test_create_parent_output_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_reference_pipeline(
                FIXTURE,
                "cooccurrence",
                root / "nested" / "neighbors.csv",
                root / "nested" / "recommendations.csv",
                root / "nested" / "stats.json",
            )
            self.assertTrue((root / "nested" / "neighbors.csv").is_file())
            self.assertTrue((root / "nested" / "recommendations.csv").is_file())
            self.assertTrue((root / "nested" / "stats.json").is_file())

    def test_reject_top_k_less_than_one(self) -> None:
        with self.assertRaisesRegex(ItemCFError, "top-k"):
            validate_positive_parameters(1, 1, 0)

    def test_reject_top_l_less_than_one(self) -> None:
        with self.assertRaisesRegex(ItemCFError, "top-l"):
            validate_positive_parameters(1, 0, 1)

    def test_reject_min_common_users_less_than_one(self) -> None:
        with self.assertRaisesRegex(ItemCFError, "min-common-users"):
            validate_positive_parameters(0, 1, 1)

    def test_repeated_runs_produce_logically_equivalent_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = [
                root / "neighbors.csv",
                root / "recommendations.csv",
                root / "stats.json",
            ]
            run_reference_pipeline(FIXTURE, "cosine", outputs[0], outputs[1], outputs[2])
            first = [path.read_bytes() for path in outputs]
            run_reference_pipeline(FIXTURE, "cosine", outputs[0], outputs[1], outputs[2])
            second = [path.read_bytes() for path in outputs]
            self.assertEqual(first, second)

    def test_reject_input_file_that_does_not_exist(self) -> None:
        with self.assertRaisesRegex(ItemCFError, "does not exist"):
            load_normalized_ratings(Path("missing-ratings.csv"))

    def test_reject_input_path_that_is_not_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ItemCFError, "not a file"):
                load_normalized_ratings(Path(tmp))

    def test_cli_help_parser_accepts_required_arguments(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "--input",
                "ratings.csv",
                "--method",
                "cosine",
                "--neighbors-output",
                "neighbors.csv",
                "--recommendations-output",
                "recommendations.csv",
                "--stats-output",
                "stats.json",
            ]
        )
        self.assertEqual(args.method, "cosine")
        self.assertEqual(args.min_common_users, 1)

    def test_parse_positive_int_rejects_zero(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_positive_int("0")

    def test_build_statistics_counts_users_items_and_duplicates(self) -> None:
        result, histories, pair_stats = self.load_fixture()
        similarities, eligible = compute_directed_similarities(pair_stats, "cosine", 1)
        retained = retain_top_l_neighbors(similarities, 50)
        recommendations = generate_top_k_recommendations(histories, retained, 10)
        stats = build_statistics(
            "cosine",
            "ratings.csv",
            result,
            histories,
            pair_stats,
            eligible,
            similarities,
            retained,
            recommendations,
            1,
            50,
            10,
        )
        self.assertEqual(stats["users"], 4)
        self.assertEqual(stats["items"], 4)
        self.assertEqual(stats["exact_duplicate_rows_ignored"], 1)


if __name__ == "__main__":
    unittest.main()
