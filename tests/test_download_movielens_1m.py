import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

from scripts import download_movielens_1m as dl


class DownloadMovieLensTests(unittest.TestCase):
    def make_zip_bytes(self, traversal: bool = False) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("ml-1m/ratings.dat", "1::1::5::978300760\n")
            archive.writestr("ml-1m/movies.dat", "1::Movie (2000)::Drama\n")
            archive.writestr("ml-1m/users.dat", "1::F::1::10::48067\n")
            archive.writestr("ml-1m/README", "README\n")
            if traversal:
                archive.writestr("../evil.txt", "bad\n")
        return buffer.getvalue()

    def write_zip(self, path: Path, traversal: bool = False) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.make_zip_bytes(traversal=traversal))
        return path

    def test_no_network_call_when_verify_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_zip(root / "ml-1m.zip")
            dl.extract_archive(root / "ml-1m.zip", root)
            with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network disabled")):
                manifest = dl.download_movielens_1m(root, verify_only=True)
            self.assertEqual(manifest["dataset_name"], "MovieLens 1M")

    def test_zip_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self.write_zip(root / "ml-1m.zip", traversal=True)
            with self.assertRaisesRegex(dl.MovieLensDownloadError, "Unsafe ZIP"):
                dl.validate_zip_structure(archive, root)

    def test_partial_download_is_not_treated_as_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ml-1m.zip.part").write_text("partial", encoding="utf-8")
            with self.assertRaisesRegex(dl.MovieLensDownloadError, "Partial archive"):
                dl.download_movielens_1m(root, verify_only=True)

    def test_existing_verified_data_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_zip(root / "ml-1m.zip")
            dl.extract_archive(root / "ml-1m.zip", root)
            with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network disabled")):
                manifest = dl.download_movielens_1m(root)
            self.assertTrue(manifest["reused_existing_archive"])

    def test_force_replaces_existing_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ml-1m.zip").write_text("not zip", encoding="utf-8")
            with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(self.make_zip_bytes())):
                manifest = dl.download_movielens_1m(root, force=True)
            self.assertEqual(manifest["archive"]["archive_name"], "ml-1m.zip")
            self.assertTrue((root / "ml-1m" / "ratings.dat").is_file())

    def test_verify_only_behavior_requires_existing_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(dl.MovieLensDownloadError, "Missing extracted"):
                dl.download_movielens_1m(Path(tmp), verify_only=True)

    def test_manifest_contains_no_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_zip(root / "ml-1m.zip")
            dl.extract_archive(root / "ml-1m.zip", root)
            manifest = dl.download_movielens_1m(root, verify_only=True)
            text = json.dumps(manifest, sort_keys=True)
            self.assertNotIn(str(root), text)
            self.assertIn("ml-1m/ratings.dat", text)


if __name__ == "__main__":
    unittest.main()
