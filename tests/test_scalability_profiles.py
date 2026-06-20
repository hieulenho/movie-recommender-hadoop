import copy
import unittest
from pathlib import Path

from scripts.run_scalability_experiments import BenchmarkError, load_profiles, validate_profiles


PROFILES_FILE = Path("config/scalability_profiles.json")


class ScalabilityProfilesTests(unittest.TestCase):
    def load_builtin(self) -> dict[str, object]:
        return load_profiles(PROFILES_FILE)

    def first_experiment(self, data: dict[str, object]) -> dict[str, object]:
        profiles = data["profiles"]
        return profiles[0]["experiments"][0]  # type: ignore[index]

    def assert_invalid(self, data: dict[str, object], pattern: str) -> None:
        with self.assertRaisesRegex(BenchmarkError, pattern):
            validate_profiles(data)

    def test_loading_all_builtin_profiles(self) -> None:
        data = self.load_builtin()
        names = [profile["name"] for profile in data["profiles"]]  # type: ignore[index]
        self.assertEqual(names, ["smoke", "standard", "extended"])

    def test_required_smoke_profile_exists(self) -> None:
        data = self.load_builtin()
        names = {profile["name"] for profile in data["profiles"]}  # type: ignore[index]
        self.assertIn("smoke", names)

    def test_dataset_sizes_increase_within_each_profile_and_method(self) -> None:
        data = self.load_builtin()
        for profile in data["profiles"]:  # type: ignore[index]
            by_method: dict[str, list[int]] = {}
            for experiment in profile["experiments"]:
                by_method.setdefault(experiment["method"], []).append(
                    experiment["users"] * experiment["ratings_per_user"]
                )
            for sizes in by_method.values():
                self.assertEqual(sizes, sorted(sizes))
                self.assertGreater(len(set(sizes)), 1)

    def test_reject_duplicate_experiment_ids(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        experiments = data["profiles"][0]["experiments"]  # type: ignore[index]
        experiments[1]["id"] = experiments[0]["id"]
        self.assert_invalid(data, "Duplicate experiment ID")

    def test_reject_unsupported_similarity_method(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        self.first_experiment(data)["method"] = "pearson"
        self.assert_invalid(data, "Unsupported similarity method")

    def test_reject_invalid_top_l(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        self.first_experiment(data)["top_l"] = 0
        self.assert_invalid(data, "top_l")

    def test_reject_invalid_top_k(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        self.first_experiment(data)["top_k"] = 0
        self.assert_invalid(data, "top_k")

    def test_reject_invalid_min_common_users(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        self.first_experiment(data)["min_common_users"] = 0
        self.assert_invalid(data, "min_common_users")

    def test_reject_invalid_relevance_threshold(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        self.first_experiment(data)["relevance_threshold"] = 6
        self.assert_invalid(data, "relevance_threshold")

    def test_reject_invalid_reducer_count(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        self.first_experiment(data)["reducers"] = 0
        self.assert_invalid(data, "reducers")

    def test_reject_invalid_repetition_count(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        self.first_experiment(data)["repetitions"] = 0
        self.assert_invalid(data, "repetitions")

    def test_reject_duplicate_profile_names(self) -> None:
        data = copy.deepcopy(self.load_builtin())
        data["profiles"][1]["name"] = data["profiles"][0]["name"]  # type: ignore[index]
        self.assert_invalid(data, "Duplicate profile name")

    def test_smoke_profile_contains_both_methods(self) -> None:
        data = self.load_builtin()
        smoke = data["profiles"][0]  # type: ignore[index]
        methods = {experiment["method"] for experiment in smoke["experiments"]}
        self.assertEqual(methods, {"cosine", "cooccurrence"})


if __name__ == "__main__":
    unittest.main()
