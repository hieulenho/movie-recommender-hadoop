import tempfile
import unittest
from pathlib import Path

from demo.artifact_paths import (
    FULL_REFERENCE_DEFAULTS,
    build_local_artifact_defaults,
    required_artifact_errors,
    resolve_artifact_path,
    resolve_paths_for_loading,
)


class DemoArtifactPathTests(unittest.TestCase):
    def touch(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")

    def test_full_reference_defaults_resolve_relative_to_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for key, relative in FULL_REFERENCE_DEFAULTS.items():
                if key in {"user_history", "recommendations"}:
                    (root / relative).mkdir(parents=True)
                else:
                    self.touch(root / relative)

            defaults = build_local_artifact_defaults(root)

            self.assertEqual(defaults["user_history"], "results/full-reference-dataset/cosine/user-history")
            self.assertEqual(defaults["recommendations"], "results/full-reference-dataset/cosine/recommendations")
            self.assertFalse(Path(defaults["user_history"]).is_absolute())

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
            self.assertIn("Lịch sử người dùng", errors[0])
            self.assertIn("Ví dụ full-reference", errors[0])
            self.assertNotIn("Traceback", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
