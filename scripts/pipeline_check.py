#!/usr/bin/env python3
"""Delivery gate for messenger-pipeline: WeChat HTML structure + docx cross-check.

Usage:
  python pipeline_check.py --html article.wechat.html --docx draft.docx --theme kami [--json]

Exit code 0 only when every check passes.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL_CANDIDATES = (
    Path.home() / ".claude" / "skills",
    Path.home() / ".config" / "magpie" / "library" / "skills",
)


def find_skill(name: str) -> Path | None:
    for base in SKILL_CANDIDATES:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def check_html(html_path: Path, docx_path: Path | None, theme: str) -> dict:
    html = html_path.read_text(encoding="utf-8")
    counts = {
        "style_tags": html.count("<style"),
        "external_urls": len(re.findall(r"https?://", html)),
        "font_family": html.count("font-family"),
        "thead": html.count("<thead"),
        "tbody": html.count("<tbody"),
        "h2": html.count("<h2"),
        "td": html.count("<td"),
        "images": html.count("data:image"),
    }
    issues: list[str] = []

    for key in ("style_tags", "external_urls", "font_family", "thead", "tbody"):
        if counts[key]:
            issues.append(f"{key} must be 0, found {counts[key]}")
    if counts["h2"] == 0:
        issues.append("no <h2> found: heading levels likely collapsed to body text")

    skill = find_skill("wechat-article-html")
    if skill is None:
        issues.append("wechat-article-html skill not found; validate_html.py was not run")
    else:
        result = subprocess.run(
            [sys.executable, str(skill / "scripts" / "validate_html.py"), str(html_path), "--theme", theme],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip().splitlines()[-8:]
            issues.append("validate_html.py failed: " + " | ".join(detail))

    docx_stats = {}
    if docx_path is not None:
        from docx import Document

        doc = Document(str(docx_path))
        docx_stats = {"tables": len(doc.tables), "inline_images": len(doc.inline_shapes)}
        if docx_stats["tables"] and counts["td"] == 0:
            issues.append(f"docx has {docx_stats['tables']} table(s) but HTML has no <td>: tables were dropped")
        if docx_stats["inline_images"] and counts["images"] < docx_stats["inline_images"]:
            issues.append(
                f"docx has {docx_stats['inline_images']} inline image(s) but HTML has "
                f"{counts['images']} data:image(s): figures were dropped"
            )

    return {
        "html": str(html_path),
        "theme": theme,
        "counts": counts,
        "docx": docx_stats,
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--docx", type=Path, default=None)
    parser.add_argument("--theme", required=True, help="kami | esther | punk")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    args = parser.parse_args()

    if not args.html.is_file():
        print(f"FAIL: HTML not found: {args.html}")
        return 1
    if args.docx is not None and not args.docx.is_file():
        print(f"FAIL: docx not found: {args.docx}")
        return 1

    report = check_html(args.html, args.docx, args.theme)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"HTML gate: {report['status']}")
        print("counts:", json.dumps(report["counts"], ensure_ascii=False))
        if report["docx"]:
            print("docx:", json.dumps(report["docx"], ensure_ascii=False))
        for issue in report["issues"]:
            print("  FAIL:", issue)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
