#!/usr/bin/env python3
"""Mirror Adobe's published documentation skill without executing archive content."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


INDEX_URL = "https://react-aria.adobe.com/.well-known/agent-skills/index.json"
ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_CONTENT_BYTES = 64 * 1024 * 1024
MAX_FILES = 2000


def approved_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "react-aria.adobe.com"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("Only HTTPS downloads from react-aria.adobe.com are allowed")
    return url


class AdobeRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        approved_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download(url: str, limit: int) -> bytes:
    approved_url(url)
    request = Request(url, headers={"User-Agent": "react-aria-skill-mirror/1.0"})
    with build_opener(AdobeRedirects()).open(request, timeout=60) as response:
        approved_url(response.geturl())
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Download exceeds size limit")
    return data


def select_artifact(index: dict) -> tuple[str, str]:
    entries = [entry for entry in index["skills"] if entry.get("name") == "react-aria"]
    if len(entries) != 1 or entries[0].get("type") != "archive":
        raise ValueError("Expected exactly one react-aria archive")
    entry = entries[0]
    digest = entry.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Missing or invalid SHA-256 digest")
    return approved_url(urljoin(INDEX_URL, entry["url"])), digest


def verified_files(archive: bytes, digest: str) -> dict[str, bytes]:
    if "sha256:" + hashlib.sha256(archive).hexdigest() != digest:
        raise ValueError("Archive SHA-256 digest mismatch")
    files: dict[str, bytes] = {}
    total_size = 0
    members_seen = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        for member in bundle:
            members_seen += 1
            if members_seen > MAX_FILES * 2:
                raise ValueError("Too many archive entries")
            name = member.name
            if name.startswith("./"):
                name = name[2:]
            path = PurePosixPath(name)
            if (
                not name
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or "\x00" in name
                or str(path) != name
            ):
                raise ValueError("Unsafe archive path")
            if member.isdir():
                if path.parts[0] != "references":
                    raise ValueError("Unexpected archive directory")
                continue
            if not member.isfile():
                raise ValueError("Archive contains a link or special file")
            if name not in ("SKILL.md", "LICENSE", "NOTICE") and path.parts[0] != "references":
                raise ValueError("Unexpected top-level archive file")
            if name in files:
                raise ValueError("Duplicate archive file")
            total_size += member.size
            if total_size > MAX_CONTENT_BYTES or len(files) >= MAX_FILES:
                raise ValueError("Expanded archive exceeds size limit")
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError("Unreadable archive file")
            content = source.read()
            content.decode("utf-8")
            files[name] = content
    if "SKILL.md" not in files or not any(name.startswith("references/") for name in files):
        raise ValueError("Archive is missing the skill or its references")
    skill = files["SKILL.md"].decode("utf-8")
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", skill, re.DOTALL)
    if frontmatter is None or not re.search(
        r"""^name:\s*(?:react-aria|"react-aria"|'react-aria')\s*$""",
        frontmatter.group(1),
        re.MULTILINE,
    ):
        raise ValueError("Invalid react-aria skill metadata")
    return files


def install(root: Path, files: dict[str, bytes], archive_url: str, digest: str) -> bool:
    """Stage and replace only the mirrored directory; retain repository automation."""
    destination = root / "skills" / "react-aria"
    if (root / "skills").is_symlink() or destination.is_symlink():
        raise ValueError("Refusing to replace a symlink")
    manifest = {
        "skill": "react-aria",
        "index_url": INDEX_URL,
        "archive_url": archive_url,
        "archive_digest": digest,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    current = (
        {p.relative_to(destination).as_posix(): p.read_bytes()
         for p in destination.rglob("*") if p.is_file()}
        if destination.exists() else {}
    )
    manifest_path = root / "upstream.json"
    if current == files and manifest_path.exists() and manifest_path.read_bytes() == manifest_bytes:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sync-", dir=root) as temporary:
        stage = Path(temporary) / "stage"
        stage.mkdir()
        for name, data in files.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        backup = Path(temporary) / "previous"
        existed = destination.exists()
        if existed:
            destination.rename(backup)
        try:
            stage.rename(destination)
        except BaseException:
            if existed:
                backup.rename(destination)
            raise
        staged_manifest = Path(temporary) / "upstream.json"
        staged_manifest.write_bytes(manifest_bytes)
        staged_manifest.replace(manifest_path)
    return True


def main() -> None:
    index = json.loads(download(INDEX_URL, 1024 * 1024))
    archive_url, digest = select_artifact(index)
    files = verified_files(download(archive_url, MAX_ARCHIVE_BYTES), digest)
    changed = install(ROOT, files, archive_url, digest)
    print(f"{'Updated' if changed else 'Already current'}: {len(files)} files; {digest}")


if __name__ == "__main__":
    main()
