#!/usr/bin/env python3
"""Check that relative Markdown links in docs point to existing files.

Scans README.md and all docs/*.md files for relative links of the form
[text](path) and verifies each path exists on disk.  Exits with code 1 if
any broken links are found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

# Markdown link pattern: [text](target) where target does not start with http
_LINK_RE = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")

# Files to scan
SCAN_FILES = [REPO_ROOT / "README.md"] + sorted(DOCS_DIR.glob("*.md"))


def check_file(md_file: Path) -> list[str]:
    """Return a list of broken-link error strings for *md_file*."""
    errors: list[str] = []
    text = md_file.read_text(encoding="utf-8")
    for match in _LINK_RE.finditer(text):
        target = match.group(1)
        # Skip external URLs, anchors, and mailto links
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # Strip any fragment from the path
        path_part = target.split("#")[0]
        if not path_part:
            continue
        # Resolve relative to the directory containing the markdown file
        resolved = (md_file.parent / path_part).resolve()
        if not resolved.exists():
            errors.append(f"  {md_file.relative_to(REPO_ROOT)}: broken link -> {target!r}")
    return errors


def main() -> None:
    all_errors: list[str] = []
    for md_file in SCAN_FILES:
        if md_file.exists():
            all_errors.extend(check_file(md_file))

    if all_errors:
        print("Doc-link check FAILED - broken relative links found:")
        for err in all_errors:
            print(err)
        sys.exit(1)
    else:
        scanned = [f.name for f in SCAN_FILES if f.exists()]
        print(f"Doc-link check PASSED - scanned: {', '.join(scanned)}")


if __name__ == "__main__":
    main()
