import importlib
import pathlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
jardistribution = importlib.import_module("mx._impl.mx_jardistribution")
benchmark = importlib.import_module("mx._impl.mx_benchmark")


class JarManifestTest(unittest.TestCase):
    def test_folded_attributes(self):
        packages = ["java.base/" + "a" * 50, "java.base/" + "b" * 50]
        entries = {
            "Add-Opens": " ".join(packages),
            "At-Limit": "a" * 62,
            "Long-Value": "abé界" * 200,
        }
        with tempfile.TemporaryDirectory() as directory:
            for exploded in (False, True):
                with self.subTest(exploded=exploded):
                    path = pathlib.Path(directory) / ("exploded" if exploded else "test.jar")
                    archive = jardistribution._Archive(None, str(path), exploded, zipfile.ZIP_STORED)
                    archive.finalize_archive_or_directory(entries.copy())
                    if exploded:
                        data = (path / "META-INF/MANIFEST.MF").read_bytes()
                    else:
                        with zipfile.ZipFile(path) as jar:
                            data = jar.read("META-INF/MANIFEST.MF")

                    data = data.replace(b"\r\n", b"\n")
                    self.assertTrue(all(len(line) <= 72 for line in data.splitlines()))
                    self.assertIn(b"At-Limit: " + b"a" * 62 + b"\n", data)
                    unfolded = data.replace(b"\n ", b"").decode("utf-8").splitlines()
                    expected = ["Manifest-Version: 1.0"] + [f"{k}: {v}" for k, v in entries.items()]
                    self.assertEqual(unfolded, expected)
                    self.assertEqual(
                        benchmark._add_opens_and_exports_from_manifest(str(path)),
                        [f"--add-opens={package}=ALL-UNNAMED" for package in packages],
                    )

    def test_jdk_continuation_splits_utf8(self):
        package = "java.base/" + "a" * 48 + "é"
        header = f"Add-Exports: {package}".encode("utf-8")
        self.assertEqual(header[71:73], "é".encode("utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.jar"
            with zipfile.ZipFile(path, "w") as jar:
                jar.writestr("META-INF/MANIFEST.MF", header[:72] + b"\r\n " + header[72:] + b"\r\n")
            self.assertEqual(
                benchmark._add_opens_and_exports_from_manifest(str(path)),
                [f"--add-exports={package}=ALL-UNNAMED"],
            )
