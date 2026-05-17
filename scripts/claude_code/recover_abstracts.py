#!/usr/bin/env python3
"""
One-shot recovery: backfill 'No abstract available.' entries in README.md.

For every paper block in README.md whose abstract is the literal
'No abstract available.', extract the arXiv ID from the title URL
(https://arxiv.org/abs/<ID>), query the public arxiv.org Atom API for that
ID, and replace the placeholder with the real abstract. Entries without an
arXiv ID in the title URL (e.g. ones still pointing to Semantic Scholar)
are left untouched.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}

ENTRY_START = re.compile(r"^🔹 \[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)", re.M)
ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([\w./-]+?)(?:v\d+)?$")
NO_ABSTRACT_LINE = "    No abstract available.\n"


def split_blocks(text: str) -> list[tuple[int, int, str]]:
    """Return list of (start, end, block_text) for each 🔹 entry block."""
    starts = [m.start() for m in ENTRY_START.finditer(text)]
    blocks = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        blocks.append((s, e, text[s:e]))
    return blocks


def extract_arxiv_id(url: str) -> str | None:
    m = ARXIV_ID_RE.search(url)
    return m.group(1) if m else None


def fetch_abstract(arxiv_id: str) -> str | None:
    q = urllib.parse.urlencode({"id_list": arxiv_id})
    url = f"{ARXIV_API}?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "ais-readme-recovery/1.0"})
    last_err: Exception | None = None
    body = b""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
            break
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    else:
        raise last_err if last_err else RuntimeError("arxiv query failed")
    root = ET.fromstring(body)
    entry = root.find("a:entry", NS)
    if entry is None:
        return None
    summary = (entry.findtext("a:summary", default="", namespaces=NS) or "").strip()
    if not summary:
        return None
    return re.sub(r"\s+", " ", summary)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="don't write back to README.md")
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between arxiv API calls")
    ap.add_argument("--limit", type=int, default=0, help="cap number of entries (0 = all)")
    args = ap.parse_args()

    text = README.read_text(encoding="utf-8")
    blocks = split_blocks(text)

    targets: list[tuple[int, int, str, str, str]] = []  # (start, end, block, title, arxiv_id)
    skipped_no_arxiv: list[str] = []
    for s, e, block in blocks:
        if NO_ABSTRACT_LINE not in block:
            continue
        m = ENTRY_START.search(block)
        if not m:
            continue
        title = m.group("title").strip()
        url = m.group("url")
        arxiv_id = extract_arxiv_id(url)
        if not arxiv_id:
            skipped_no_arxiv.append(title)
            continue
        targets.append((s, e, block, title, arxiv_id))

    if args.limit:
        targets = targets[: args.limit]

    print(f"[recover-abstracts] {len(targets)} entries to fix, "
          f"{len(skipped_no_arxiv)} skipped (no arxiv id), sleep={args.sleep}s")
    for t in skipped_no_arxiv:
        print(f"  [skip] no-arxiv: {t}")

    # Build replacements keyed by (start, end) so we can splice in order
    replacements: list[tuple[int, int, str]] = []
    recovered = 0
    api_miss: list[str] = []
    for i, (s, e, block, title, aid) in enumerate(targets, 1):
        try:
            abstract = fetch_abstract(aid)
        except Exception as exc:
            print(f"  [{i:02d}] ! api error for {aid}: {exc!r} — skipping {title!r}")
            api_miss.append(title)
            time.sleep(args.sleep)
            continue
        if not abstract:
            print(f"  [{i:02d}] miss  {aid:<14} {title}")
            api_miss.append(title)
            time.sleep(args.sleep)
            continue
        new_line = f"    {abstract}\n"
        new_block = block.replace(NO_ABSTRACT_LINE, new_line, 1)
        replacements.append((s, e, new_block))
        recovered += 1
        print(f"  [{i:02d}] OK    {aid:<14} {title}")
        time.sleep(args.sleep)

    print()
    print(f"[recover-abstracts] recovered={recovered}  api_miss={len(api_miss)}  "
          f"skipped_no_arxiv={len(skipped_no_arxiv)}")

    if not replacements:
        print("[recover-abstracts] nothing to write")
        return 0
    if args.dry_run:
        print("[recover-abstracts] dry-run: README.md not modified")
        return 0

    # Splice replacements back into text in reverse order so offsets stay valid
    replacements.sort(key=lambda r: r[0], reverse=True)
    new_text = text
    for s, e, new_block in replacements:
        new_text = new_text[:s] + new_block + new_text[e:]
    README.write_text(new_text, encoding="utf-8")
    print(f"[recover-abstracts] wrote {README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
