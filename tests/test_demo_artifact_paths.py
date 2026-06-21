import tempfile
import unittest
from pathlib import Path

from demo.artifact_paths import (
    FULL_REFERENCE_DEFAULTS,
    MOVIELENS_DEFAULTS_BY_METHOD,
    build_dataset_method_defaults,
    build_local_artifact_defaults,
    movielens_artifacts_available,
    required_artifact_errors,
    resolve_artifact_path,
    resolve_paths_for_loading,
)


class DemoArtifactPathTests(unittest.TestCase):
    def touch(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")

    def test_movielens_defaults_resolve_relative_to_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                MOVIELENS_DEFAULTS_BY_METHOD["cosine"]["user_history"],
                MOVIELENS_DEFAULTS_BY_METHOD["cosine"]["recommendations"],
                MOVIELENS_DEFAULTS_BY_METHOD["cosine"]["evaluation"],
                MOVIELENS_DEFAULTS_BY_METHOD["cosine"]["metadata"],
            ):
                self.touch(root / relative / "part-r-00000" if relative.endswith("history") or relative.endswith("recommendations") else root / relative)

            defaults = build_local_artifact_defaults(root)

            self.assertEqual(defaults["user_history"], "results/movielens-1m/common/user-history")
            self.assertEqual(defaults["recommendations"], "results/movielens-1m/cosine/recommendations")
            self.assertFalse(Path(defaults["user_history"]).is_absolute())
            self.assertTrue(movielens_artifacts_available(root))

    def test_github_reference_defaults_remain_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            defaults = build_dataset_method_defaults("github-reference", "cooccurrence", Path(tmp))
            self.assertEqual(defaults["recommendations"], "results/full-reference-dataset/cooccurrence/recommendations")
            self.assertIn("results/full-reference-dataset", FULL_REFERENCE_DEFAULTS["recommendations"])

    def test_no_machine_specific_absolute_path_is_hard_coded(self) -> None:
        defaults = build_local_artifact_defaults(Path("missing-root"))
        joined = "\n".join(defaults.values())
        self.assertNotIn("D:\\", joined)
        self.assertNotIn("C:\\Users", joined)

    def test_empty_optional_paths_stay_empty_for_loading(self) -> None:
        resolved = resolve_paths_for_loading({"metadata": "", "benchmark": ""}, Path("repo"))
        self.assertEqual(resolved["metadata"], "")
        self.assertEqual(resolved["benchmark"], "")
        self.assertIsNone(resolve_artifact_path(Path("repo"), ""))

    def test_missing_required_paths_return_concise_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            errors = required_artifact_errors(
                {
                    "user_history": "missing/history",
                    "recommendations": "missing/recommendations",
                },
                Path(tmp),
            )
            self.assertEqual(len(errors), 2)
            self.assertIn("Missing required artifact: User history", errors[0])
            self.assertIn("Example:", errors[0])
            self.assertNotIn("Traceback", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
