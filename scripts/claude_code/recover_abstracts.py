#!/usr/bin/env python3
"""
One-shot recovery: backfill 'No abstract available.' entries in README.md.

For every paper block in README.md whose abstract is the literal
'No abstract available.', extract the arXiv ID from the title URL
(https://arxiv.org/abs/<ID>), fetch the abstract from arXiv, and replace
the placeholder. Entries without an arXiv ID in the title URL (e.g. ones
still pointing to Semantic Scholar) are left untouched.

Two arXiv sources are tried in order, because they have independent
rate-limit pools:
  1. The Atom API at export.arxiv.org/api/query (machine-friendly XML).
  2. The HTML page at arxiv.org/abs/<id> (parsed via regex).
If the Atom API returns HTTP 429 or an empty summary, the HTML page is
used as a fallback.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ARXIV_ATOM = "https://export.arxiv.org/api/query"
ARXIV_ABS = "https://arxiv.org/abs/"
NS = {"a": "http://www.w3.org/2005/Atom"}
UA = "ais-readme-recovery/1.0"

ENTRY_START = re.compile(r"^🔹 \[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)", re.M)
ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([\w./-]+?)(?:v\d+)?$")
NO_ABSTRACT_LINE = "    No abstract available.\n"
HTML_ABSTRACT_RE = re.compile(
    r'<blockquote[^>]*class="abstract[^"]*"[^>]*>(.*?)</blockquote>', re.S
)


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


def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_atom(arxiv_id: str) -> str | None:
    """Single Atom-API attempt. Returns abstract or None. Raises on HTTP error
    so the caller can decide whether to fall back to HTML."""
    q = urllib.parse.urlencode({"id_list": arxiv_id})
    body = _http_get(f"{ARXIV_ATOM}?{q}")
    root = ET.fromstring(body)
    entry = root.find("a:entry", NS)
    if entry is None:
        return None
    summary = (entry.findtext("a:summary", default="", namespaces=NS) or "").strip()
    if not summary:
        return None
    return re.sub(r"\s+", " ", summary)


def _fetch_html(arxiv_id: str) -> str | None:
    """Scrape abstract from the HTML abs page. Different rate-limit pool than
    the Atom API, so this works when the API returns 429."""
    body = _http_get(f"{ARXIV_ABS}{arxiv_id}")
    html = body.decode("utf-8", errors="replace")
    m = HTML_ABSTRACT_RE.search(html)
    if not m:
        return None
    txt = re.sub(r"<[^>]+>", " ", m.group(1))
    txt = re.sub(r"^\s*Abstract:\s*", "", txt, count=1)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt or None


def fetch_abstract(arxiv_id: str) -> tuple[str | None, str]:
    """Try Atom first; on 429 or empty, fall back to HTML.
    Returns (abstract_or_None, source_label) where source_label is one of
    'atom', 'html', or 'miss'."""
    try:
        result = _fetch_atom(arxiv_id)
        if result:
            return result, "atom"
        # Empty summary from Atom — try HTML in case it has the abstract
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise  # genuine non-rate-limit failure; surface it
        # 429: drop to HTML fallback without retrying Atom

    try:
        result = _fetch_html(arxiv_id)
        if result:
            return result, "html"
    except Exception:
        pass
    return None, "miss"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="don't write back to README.md")
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between arxiv calls")
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

    replacements: list[tuple[int, int, str]] = []
    recovered_atom = 0
    recovered_html = 0
    api_miss: list[str] = []
    for i, (s, e, block, title, aid) in enumerate(targets, 1):
        try:
            abstract, source = fetch_abstract(aid)
        except Exception as exc:
            print(f"  [{i:02d}] ! error for {aid}: {exc!r} — skipping {title!r}")
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
        if source == "atom":
            recovered_atom += 1
        else:
            recovered_html += 1
        print(f"  [{i:02d}] OK[{source}] {aid:<14} {title}")
        time.sleep(args.sleep)

    print()
    print(f"[recover-abstracts] recovered={recovered_atom + recovered_html} "
          f"(atom={recovered_atom}, html={recovered_html})  "
          f"miss={len(api_miss)}  skipped_no_arxiv={len(skipped_no_arxiv)}")

    if not replacements:
        print("[recover-abstracts] nothing to write")
        return 0
    if args.dry_run:
        print("[recover-abstracts] dry-run: README.md not modified")
        return 0

    replacements.sort(key=lambda r: r[0], reverse=True)
    new_text = text
    for s, e, new_block in replacements:
        new_text = new_text[:s] + new_block + new_text[e:]
    README.write_text(new_text, encoding="utf-8")
    print(f"[recover-abstracts] wrote {README}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
