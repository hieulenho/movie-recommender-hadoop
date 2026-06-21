import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_submission_package import build_submission_package, is_excluded


class SubmissionPackageTests(unittest.TestCase):
    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_git(self, root: Path, *args: str) -> None:
        completed = subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_excludes_generated_and_raw_paths(self) -> None:
        self.assertTrue(is_excluded("data/raw/github-reference/mv_0000001.txt"))
        self.assertTrue(is_excluded("results/full-reference-dataset/method_comparison.csv"))
        self.assertTrue(is_excluded("target/final-report-data/final_report_facts.json"))
        self.assertFalse(is_excluded("scripts/build_submission_package.py"))

    def test_builds_zip_without_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write(root / "README.md", "demo\n")
            self.write(root / "scripts" / "tool.py", "print('ok')\n")
            self.write(root / "docs" / "guide.md", "# Guide\n")
            self.write(root / "data" / "raw" / "secret.txt", "raw\n")
            self.write(root / "results" / "out.txt", "generated\n")
            self.run_git(root, "init")
            self.run_git(root, "add", "README.md", "scripts/tool.py", "docs/guide.md", "data/raw/secret.txt", "results/out.txt")

            output = root / "dist" / "package.zip"
            manifest = build_submission_package(root, output)

            self.assertEqual(manifest["file_count"], 3)
            with zipfile.ZipFile(output, "r") as archive:
                names = set(archive.namelist())
            self.assertIn("README.md", names)
            self.assertIn("SUBMISSION_MANIFEST.json", names)
            self.assertNotIn("data/raw/secret.txt", names)
            self.assertNotIn("results/out.txt", names)


if __name__ == "__main__":
    unittest.main()
