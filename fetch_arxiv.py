#!/usr/bin/env python3
"""Fetch a paper from arXiv and insert it into README.md under a topic section.

Replaces the deprecated Semantic-Scholar-based fetch_semantic_info.py (which
predates the topic-section layout). Stdlib-only, arXiv-first, and it never
touches git: review the diff yourself and commit/push manually.

Usage:
    python fetch_arxiv.py --id 2609.24972 --section "Self-Improvement and RSI" \
        --tldr "One-line summary." [--code URL] [--publisher-note "accepted to X"] [--dry-run]

Notes:
  - Uses the lenient arxiv.org/abs/<id> HTML page (the export.arxiv.org Atom API
    rate-limits aggressively; never retry on a 429).
  - Inserts at the TOP of the section (sections are newest-first) and bumps the
    section's count in the TOC.
  - Refuses to insert a paper whose arXiv id is already present.
"""
import argparse, html, re, sys, urllib.request

ENTRY_TEMPLATE = """🔹 [{title}](https://arxiv.org/abs/{id})
- 🔗 **arXiv PDF Link:** [Paper Link](https://arxiv.org/pdf/{id})
{code_line}- 👤 **Authors:** {authors}
- 🗓️ **Date:** {date}
- 📑 **Publisher:** {publisher}
- 💡 **TL;DR:** {tldr}
- 📝 **Abstract:**
    <details>
    <summary>Expand</summary>
    {abstract}
    </details>
"""

MONTHS = {m: i for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def clean(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip())


def fetch_arxiv(arxiv_id):
    url = f"https://arxiv.org/abs/{arxiv_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    title = clean(re.search(r'<h1 class="title[^"]*">(.*?)</h1>', page, re.S).group(1))
    title = re.sub(r"^Title:\s*", "", title)
    authors = clean(re.search(r'<div class="authors">(.*?)</div>', page, re.S).group(1))
    authors = re.sub(r"^Authors:\s*", "", authors)
    abstract = clean(re.search(
        r'<blockquote[^>]*class="abstract[^"]*"[^>]*>(.*?)</blockquote>', page, re.S).group(1))
    abstract = re.sub(r"^Abstract:\s*", "", abstract)
    d, mon, y = re.search(r"Submitted on (\d+) (\w+) (\d{4})", page).groups()
    date = f"{y}-{MONTHS[mon[:3]]:02d}-{int(d):02d}"
    return title, authors, abstract, date


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="arXiv id, e.g. 2609.24972")
    ap.add_argument("--section", required=True, help="exact '### ' section name")
    ap.add_argument("--tldr", default="_pending_", help="one-line TL;DR")
    ap.add_argument("--code", help="GitHub URL for an Official Code line")
    ap.add_argument("--publisher-note", help='e.g. "accepted to Findings of EMNLP 2026"')
    ap.add_argument("--readme", default="README.md")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    readme = open(a.readme, encoding="utf-8").read()
    if a.id in readme:
        sys.exit(f"refusing: arXiv id {a.id} already present in {a.readme}")

    heading = f"### {a.section}\n"
    if heading not in readme:
        names = re.findall(r"^### (.+)$", readme, re.M)
        sys.exit(f"section {a.section!r} not found. Sections: {names}")

    title, authors, abstract, date = fetch_arxiv(a.id)
    code_line = ""
    if a.code:
        name = a.code.rstrip("/").rsplit("/", 1)[-1]
        code_line = f"- 💻 **Official Code:** [{name}]({a.code})\n"
    publisher = "arXiv.org" + (f"; {a.publisher_note}" if a.publisher_note else "")
    entry = ENTRY_TEMPLATE.format(id=a.id, title=title, authors=authors, date=date,
                                  publisher=publisher, tldr=a.tldr,
                                  abstract=abstract, code_line=code_line)
    if a.dry_run:
        print(entry)
        return

    readme = readme.replace(heading, heading + "\n" + entry, 1)
    # bump TOC count
    slug = a.section.lower().replace(" ", "-")
    def bump(m):
        return f"{m.group(1)}({int(m.group(2)) + 1})"
    readme, n = re.subn(rf"(\[{re.escape(a.section)}\]\(#{re.escape(slug)}\) )\((\d+)\)",
                        bump, readme, count=1)
    if n != 1:
        print("warning: TOC count not updated; fix manually", file=sys.stderr)
    open(a.readme, "w", encoding="utf-8").write(readme)
    print(f"inserted {a.id} ({title[:60]}...) into '{a.section}' with date {date}")
    print("review `git diff`, then commit and push yourself (this script never pushes).")


if __name__ == "__main__":
    main()
