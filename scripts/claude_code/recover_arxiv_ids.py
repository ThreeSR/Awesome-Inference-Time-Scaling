#!/usr/bin/env python3
"""
One-shot recovery for issue #13.

Scan README.md for entries whose arxiv URL is the literal arxiv.org/abs/N/A,
look the paper up on the public arxiv.org Atom API by title, and rewrite the
URL in place when the top result has the same normalized title. Entries with
no unambiguous match are left untouched.
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

ENTRY_RE = re.compile(
    r"🔹 \[(?P<title>[^\]]+)\]\(https://arxiv\.org/abs/N/A\)\n"
    r"- 🔗 \*\*arXiv PDF Link:\*\* \[Paper Link\]\(https://arxiv\.org/pdf/N/A\)"
)


def normalize(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def to_query(title: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def query_arxiv(title: str, max_results: int = 5) -> list[tuple[str, str]]:
    q = urllib.parse.urlencode({
        "search_query": f'ti:"{to_query(title)}"',
        "max_results": str(max_results),
    })
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
    out: list[tuple[str, str]] = []
    for entry in root.findall("a:entry", NS):
        e_title = (entry.findtext("a:title", default="", namespaces=NS) or "").strip()
        e_id = (entry.findtext("a:id", default="", namespaces=NS) or "").strip()
        m = re.search(r"arxiv\.org/abs/([\w./-]+?)(?:v\d+)?$", e_id)
        if m:
            out.append((e_title, m.group(1)))
    return out


def pick_unique(title: str, results: list[tuple[str, str]]) -> str | None:
    norm_t = normalize(title)
    matches = [aid for r_title, aid in results if normalize(r_title) == norm_t]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="don't write back to README.md")
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between arxiv API calls")
    ap.add_argument("--limit", type=int, default=0, help="cap number of entries (0 = all)")
    args = ap.parse_args()

    text = README.read_text(encoding="utf-8")
    matches = list(ENTRY_RE.finditer(text))
    if args.limit:
        matches = matches[: args.limit]
    print(f"[recover] {len(matches)} broken entries to process (sleep={args.sleep}s)")

    new_parts: list[str] = []
    last = 0
    recovered: list[tuple[str, str]] = []
    skipped: list[str] = []

    for i, m in enumerate(matches, 1):
        new_parts.append(text[last:m.start()])
        block = m.group(0)
        title = m.group("title").strip()
        try:
            results = query_arxiv(title)
        except Exception as e:
            print(f"  [{i:02d}] ! API error: {e!r} — skipping {title!r}")
            new_parts.append(block)
            skipped.append(title)
            last = m.end()
            time.sleep(args.sleep)
            continue
        aid = pick_unique(title, results)
        if aid:
            new_block = (
                block.replace("arxiv.org/abs/N/A", f"arxiv.org/abs/{aid}")
                     .replace("arxiv.org/pdf/N/A", f"arxiv.org/pdf/{aid}")
            )
            new_parts.append(new_block)
            recovered.append((aid, title))
            print(f"  [{i:02d}] OK   {aid:<20} {title}")
        else:
            new_parts.append(block)
            skipped.append(title)
            n = len([1 for r_t, _ in results if normalize(r_t) == normalize(title)])
            tag = "ambig" if n > 1 else "miss"
            print(f"  [{i:02d}] {tag:<5} (results={len(results)})  {title}")
        last = m.end()
        time.sleep(args.sleep)

    new_parts.append(text[last:])
    new_text = "".join(new_parts)

    print()
    print(f"[recover] recovered={len(recovered)}  left_untouched={len(skipped)}")
    if recovered and not args.dry_run:
        README.write_text(new_text, encoding="utf-8")
        print(f"[recover] wrote {README}")
    elif args.dry_run:
        print("[recover] dry-run: README.md not modified")
    else:
        print("[recover] nothing recovered; README.md untouched")

    return 0


if __name__ == "__main__":
    sys.exit(main())
