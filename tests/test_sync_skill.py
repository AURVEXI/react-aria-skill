import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "sync_skill", Path(__file__).resolve().parents[1] / "scripts" / "sync_skill.py"
)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

SKILL = b'---\nname: "react-aria"\ndescription: "Official fixture"\n---\n# React Aria\n'
VALID = {"SKILL.md": SKILL, "references/components/Button.md": b"# Button\n"}


def archive(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for name, content in entries:
            member = tarfile.TarInfo(name)
            if isinstance(content, bytes):
                member.size = len(content)
                bundle.addfile(member, io.BytesIO(content))
            else:
                member.type = content[0]
                member.linkname = "/etc/passwd"
                bundle.addfile(member)
    data = buffer.getvalue()
    return data, "sha256:" + hashlib.sha256(data).hexdigest()


class ValidationTests(unittest.TestCase):
    def test_valid_archive(self):
        self.assertEqual(sync.verified_files(*archive(VALID.items())), VALID)

    def test_checksum_failure(self):
        data, _ = archive(VALID.items())
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            sync.verified_files(data, "sha256:" + "0" * 64)

    def test_unsafe_paths(self):
        for name in ("../escape", "/absolute", "references/../../escape", "references\\escape"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                sync.verified_files(*archive([*VALID.items(), (name, b"bad")]))

    def test_links_and_special_files(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                sync.verified_files(*archive([*VALID.items(), ("references/link", (kind,))]))

    def test_duplicate_files(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            sync.verified_files(*archive([*VALID.items(), ("SKILL.md", SKILL)]))

    def test_disallows_top_level_automation(self):
        with self.assertRaisesRegex(ValueError, "Unexpected top-level"):
            sync.verified_files(*archive([*VALID.items(), (".github/workflows/pwn.yml", b"bad")]))

    def test_requires_skill_and_references(self):
        for entries in ([("SKILL.md", SKILL)], [("references/a.md", b"a")]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                sync.verified_files(*archive(entries))

    def test_wrong_skill_name(self):
        with self.assertRaisesRegex(ValueError, "metadata"):
            sync.verified_files(*archive([
                ("SKILL.md", SKILL.replace(b"react-aria", b"other-skill")),
                ("references/a.md", b"a"),
            ]))

    def test_expansion_limit(self):
        with patch.object(sync, "MAX_CONTENT_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "size limit"):
                sync.verified_files(*archive(VALID.items()))

    def test_file_count_limit(self):
        with patch.object(sync, "MAX_FILES", 1):
            with self.assertRaises(ValueError):
                sync.verified_files(*archive(VALID.items()))

    def test_archive_url_allowlist(self):
        for url in (
            "http://react-aria.adobe.com/a",
            "https://evil.example/a",
            "https://react-aria.adobe.com.evil.example/a",
            "https://user@react-aria.adobe.com/a",
            "https://react-aria.adobe.com:444/a",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                sync.approved_url(url)

    def test_artifact_selection(self):
        index = {"skills": [{
            "name": "react-aria", "type": "archive",
            "url": "react-aria.tar.gz", "digest": "sha256:" + "a" * 64,
        }]}
        url, digest = sync.select_artifact(index)
        self.assertEqual(url, sync.INDEX_URL.rsplit("/", 1)[0] + "/react-aria.tar.gz")
        self.assertEqual(digest, "sha256:" + "a" * 64)
        index["skills"][0]["url"] = "https://evil.example/archive"
        with self.assertRaises(ValueError):
            sync.select_artifact(index)

    def test_rejects_invalid_index(self):
        for skills in ([], [{"name": "react-aria", "type": "skill-md"}],
                       [{"name": "react-aria", "type": "archive", "digest": "bad"}]):
            with self.subTest(skills=skills), self.assertRaises(ValueError):
                sync.select_artifact({"skills": skills})


class InstallTests(unittest.TestCase):
    def test_install_is_idempotent_and_preserves_automation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "scripts" / "keep.py"
            script.parent.mkdir()
            script.write_text("preserve me")
            args = (root, VALID, "https://react-aria.adobe.com/skill.tar.gz", "sha256:fixture")
            self.assertTrue(sync.install(*args))
            before = (root / "upstream.json").read_bytes()
            self.assertFalse(sync.install(*args))
            self.assertEqual((root / "upstream.json").read_bytes(), before)
            self.assertEqual(script.read_text(), "preserve me")
            self.assertEqual(json.loads(before)["files"]["SKILL.md"],
                             hashlib.sha256(SKILL).hexdigest())

    def test_removes_obsolete_files_and_repairs_modified_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = (root, VALID, "https://react-aria.adobe.com/skill.tar.gz", "sha256:fixture")
            sync.install(*args)
            skill = root / "skills" / "react-aria"
            (skill / "old.md").write_text("obsolete")
            (skill / "SKILL.md").write_text("modified")
            self.assertTrue(sync.install(*args))
            self.assertFalse((skill / "old.md").exists())
            self.assertEqual((skill / "SKILL.md").read_bytes(), SKILL)

    def test_symlink_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "skills").mkdir()
            (root / "skills" / "react-aria").symlink_to(root / "outside", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                sync.install(root, VALID, "https://react-aria.adobe.com/skill.tar.gz", "sha256:fixture")


if __name__ == "__main__":
    unittest.main()
