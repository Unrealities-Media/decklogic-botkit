import pathlib
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
import hashlib
from unittest.mock import patch

from release_identity import collect_archives, identity
from smoke import payload_hashes, check


class PayloadHashes(unittest.TestCase):
    def test_exact_bytes_paths_and_documentation_affect_digest(self):
        with tempfile.TemporaryDirectory(prefix="kit-payload-") as directory:
            root = pathlib.Path(directory)
            (root / "guide.md").write_bytes(b"guide\r\n")
            (root / "client.py").write_bytes(b"client\n")
            first = payload_hashes(root)
            self.assertEqual(first, payload_hashes(root))
            self.assertEqual(first["files"]["guide.md"], hashlib.sha256(b"guide\r\n").hexdigest())
            expected = json.dumps(first["files"], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
            self.assertEqual(first["sha256"], hashlib.sha256(expected).hexdigest())
            (root / "guide.md").write_bytes(b"guide\n")
            changed = payload_hashes(root)
            self.assertNotEqual(first["sha256"], changed["sha256"])
            (root / "guide.md").rename(root / "GUIDE.md")
            self.assertNotEqual(changed["sha256"], payload_hashes(root)["sha256"])

    def test_symlinks_rejected_without_platform_symlink_privileges(self):
        with tempfile.TemporaryDirectory(prefix="kit-payload-") as directory:
            root = pathlib.Path(directory)
            link = root / "link"
            link.write_text("fixture")
            original = pathlib.Path.is_symlink
            with patch.object(pathlib.Path, "is_symlink", lambda path: path == link or original(path)):
                with self.assertRaisesRegex(RuntimeError, "symlinks"):
                    payload_hashes(root)

    def test_missing_demo_fails_before_loading_library(self):
        with tempfile.TemporaryDirectory(prefix="kit-payload-") as directory:
            root = pathlib.Path(directory)
            (root / "decklogic_simlib.h").write_text("fixture")
            with self.assertRaisesRegex(RuntimeError, "DEMO pack missing"):
                check(root, root, "missing-library", "fixture", 0)


def commit(repo, path, text):
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--", path], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                    "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"], check=True, capture_output=True)


class ReleaseIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kit-identity-")
        self.addCleanup(self.temp.cleanup)
        self.private, self.public = [pathlib.Path(self.temp.name) / name for name in ("private", "public")]
        for repo in (self.private, self.public):
            subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", str(pathlib.Path(self.temp.name) / "no-hooks")], check=True, capture_output=True)
        for path in ("Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "src-tauri/botkit/src/lib.rs", "src-tauri/simlib/src/lib.rs"):
            commit(self.private, path, "fixture\n")
        commit(self.private, "src-tauri/sim/src/version.rs",
               'pub const ENGINE_VERSION: &str = "sim-engine-v213";\npub const ENGINE_ABI: u32 = 212;\n')
        commit(self.public, "simlib/python/simlib.py", "# client\n")

    def test_unrelated_private_frontend_commit_does_not_rebuild(self):
        before = identity(self.private, self.public)
        commit(self.private, "src/routes/+page.svelte", "<p>Frontend only</p>\n")
        after = identity(self.private, self.public)
        self.assertEqual(before["tag"], after["tag"])
        self.assertEqual(before["kit_sha256"], after["kit_sha256"])
        self.assertNotEqual(before["private_commit"], after["private_commit"])

    def test_unicode_version_comments_do_not_depend_on_windows_code_page(self):
        commit(self.private, "src-tauri/sim/src/version.rs",
               '// “engine” provenance — 日本語\n'
               'pub const ENGINE_VERSION: &str = "sim-engine-v213";\n'
               'pub const ENGINE_ABI: u32 = 212;\n')
        result = identity(self.private, self.public)
        self.assertEqual(result["engine"], "sim-engine-v213")
        self.assertEqual(result["abi"], 212)

    def test_non_utf8_version_output_fails_without_private_contents(self):
        path = "src-tauri/sim/src/version.rs"
        (self.private / path).write_bytes(b"// private-content-\xff\n")
        subprocess.run(["git", "-C", str(self.private), "add", "--", path],
                       check=True, capture_output=True)
        commit(self.private, "marker", "non-UTF8 version fixture\n")
        with self.assertRaisesRegex(RuntimeError, "not UTF-8") as caught:
            identity(self.private, self.public)
        self.assertNotIn("private-content", str(caught.exception))

    def test_host_change_without_engine_bump_rebuilds(self):
        before = identity(self.private, self.public)
        commit(self.private, "src-tauri/botkit/src/lib.rs", "// host update\n")
        after = identity(self.private, self.public)
        self.assertEqual(before["engine"], after["engine"])
        self.assertNotEqual(before["tag"], after["tag"])

    def test_public_wrapper_change_without_engine_bump_rebuilds(self):
        before = identity(self.private, self.public)
        commit(self.public, "simlib/python/simlib.py", "# updated client\n")
        after = identity(self.private, self.public)
        self.assertNotEqual(before["tag"], after["tag"])
        self.assertNotEqual(before["public_commit"], after["public_commit"])

    def test_include_asset_and_build_configuration_changes_rebuild(self):
        for path in ("src-tauri/sim/artifacts/demo/model.json", "bots/protocol/action-kinds.txt", ".cargo/config.toml"):
            before = identity(self.private, self.public)
            commit(self.private, path, "fixture\n")
            self.assertNotEqual(before["tag"], identity(self.private, self.public)["tag"])

    def test_missing_input_fails_closed(self):
        subprocess.run(["git", "-C", str(self.private), "rm", "Cargo.lock"], check=True, capture_output=True)
        commit(self.private, "marker", "missing lock\n")
        with self.assertRaisesRegex(RuntimeError, "Required build input absent"):
            identity(self.private, self.public)

    def test_private_export_gate_and_demo_changes_recheck_release(self):
        for path in ("bots/export-kit.mjs", "bots/sample/demo/decks.json"):
            commit(self.private, path, "old input\n")
            before = identity(self.private, self.public)
            commit(self.private, path, "changed input\n")
            after = identity(self.private, self.public)
            self.assertEqual(before["engine"], after["engine"])
            self.assertNotEqual(before["tag"], after["tag"])


class ArchiveCollection(unittest.TestCase):
    def test_collects_platform_manifests_and_rejects_mixed_source_identity(self):
        with tempfile.TemporaryDirectory(prefix="kit-archives-") as directory:
            root = pathlib.Path(directory)
            tag = "sim-engine-v213-kit-0123456789abcdef"
            for platform in ("linux-x86_64", "windows-x86_64", "macos-arm64"):
                content = json.dumps({"tag": tag, "kit_sha256": "same-full-digest",
                                      "artifact": {"platform": platform}}).encode()
                if platform == "windows-x86_64":
                    with zipfile.ZipFile(root / "windows.zip", "w") as archive:
                        archive.writestr("kit/release-manifest.json", content)
                else:
                    with tarfile.open(root / (platform + ".tar.gz"), "w:gz") as archive:
                        member = tarfile.TarInfo("kit/release-manifest.json")
                        member.size = len(content)
                        archive.addfile(member, io.BytesIO(content))
            result = collect_archives(root, tag)
            self.assertEqual(len(result["artifacts"]), 3)
            self.assertTrue(all(len(item["sha256"]) == 64 for item in result["artifacts"]))
            with zipfile.ZipFile(root / "windows.zip", "w") as archive:
                archive.writestr("kit/release-manifest.json", json.dumps({
                    "tag": tag, "kit_sha256": "different-full-digest",
                    "artifact": {"platform": "windows-x86_64"}}))
            with self.assertRaisesRegex(RuntimeError, "source identities differ"):
                collect_archives(root, tag)


if __name__ == "__main__":
    unittest.main()
