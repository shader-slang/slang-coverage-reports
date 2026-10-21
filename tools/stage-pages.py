#!/usr/bin/env python3
"""Build a bounded Pages site without modifying the report repository."""

import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import stat
from urllib.parse import quote


VIEWS = [f"{os_name}/new/{view}" for os_name in ("linux", "macos", "windows")
         for view in ("full", "slangc")] + ["merged/full", "merged/slangc"]
# Published sites are limited to 1 GB. Leave room for tar headers and padding.
WARN_CONTENT_BYTES = 800_000_000
MAX_CONTENT_BYTES = 950_000_000
MAX_ARCHIVE_BYTES = 1_000_000_000
OMIT = {"coverage.lcov", "coverage-report.txt", "slang-coverage-html.marker"}


def page(title, body):
    return (f'<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<title>{html.escape(title)}</title><h1>{html.escape(title)}</h1>'
            f'{body}</html>\n')


def link(url, label):
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def regular_files(root):
    """Reject links instead of following them outside a selected report."""
    if root.is_symlink():
        raise ValueError(f"Not a regular file or directory: {root}")
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(f"Not a regular file or directory: {path}")
            if stat.S_ISREG(mode):
                yield path


def stage(source, output, revision, max_bytes=MAX_CONTENT_BYTES):
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("Output must be separate from the source checkout")
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Archive revision must be a full Git commit SHA")
    latest = source / "reports/latest"
    # The source nightly permits Windows coverage to fail. Its combined summary
    # has an empty Windows entry in that case; Linux/macOS and merged views
    # remain required. A claimed Windows result must have both browsing views.
    combined = json.loads((latest / "combined-summary.json").read_text(encoding="utf-8"))
    windows_available = bool(combined["platforms"].get("windows"))
    views = [view for view in VIEWS if windows_available or not view.startswith("windows/")]
    for view in views:
        if not (latest / view / "index.html").is_file():
            raise ValueError(f"Missing current report: {view}")
    for name in ("index.html", "reports/history/index.html", "reports/slangc-coverage-trend.html"):
        if not (source / name).is_file():
            raise ValueError(f"Missing navigation page: {name}")
    output.mkdir(parents=True)
    archive = f"https://github.com/shader-slang/slang-coverage-reports/tree/{revision}/"

    def copy(path):
        destination = output / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)

    for view in views:
        for path in regular_files(latest / view):
            if path.name not in OMIT:
                copy(path)
    # Keep exports and trend data independently of detailed HTML retention.
    metadata = ["index.html", "reports/coverage-data.csv", "reports/coverage-data.json",
                "reports/slangc-coverage-history.json", "reports/slangc-coverage-trend.html"]
    for name in metadata:
        path = source / name
        if path.is_symlink():
            raise ValueError(f"Metadata is a symlink: {path}")
        if path.is_file():
            copy(path)
    history = source / "reports/history"
    for root in (latest, history):
        for path in regular_files(root):
            if path.name in {"coverage-summary.json", "combined-summary.json"}:
                copy(path)
    # Historical index metrics remain intact, but its View links lead to explicit
    # archive notices, rather than copying multi-gigabyte historical HTML trees.
    if (history / "index.html").is_file():
        copy(history / "index.html")
    for report in sorted(history.iterdir()):
        if not report.is_dir():
            continue
        entries = set()
        for path in regular_files(report):
            if path.name == "index.html":
                entries.add(path)
            elif path.name in {"coverage-summary.json", "combined-summary.json"}:
                # Some older snapshots contain only summaries. Their existing
                # history-table links still need an explicit archive notice.
                entries.add(path.parent / "index.html")
        for path in sorted(entries):
            relative = path.relative_to(source)
            home = os.path.relpath(output / "index.html", (output / relative).parent)
            write(output / relative, page("Historical coverage report",
                  '<p>This historical report is not published as source-level HTML. '
                  'The retained files are available at the Git revision below. '
                  'Clone this revision to inspect any retained HTML locally.</p><p>'
                  + link(archive + quote(relative.parent.as_posix()), "Report files at this revision")
                  + '</p><p>' + link(home, "Current coverage and historical metrics") + '</p>'))

    navigation = '<p>Current source coverage, rendered from LCOV. '
    navigation += 'The original llvm-cov / ReportGenerator HTML and raw LCOV remain in Git. '
    navigation += 'Linux/macOS source annotations use LCOV; native region detail is available '
    navigation += 'in the original reports.</p><ul>'
    navigation += ''.join('<li>' + link(view + '/index.html', view) + '</li>' for view in views)
    if not windows_available:
        navigation += '<li>Windows coverage is unavailable for this report.</li>'
    navigation += '</ul><p>' + link(archive + 'reports/latest', 'Original report files and raw coverage data') + '</p>'
    navigation += '<p>' + link('../../index.html', 'Dashboard') + ' | '
    navigation += link('../history/index.html', 'Historical metrics and archive links') + ' | '
    navigation += link('../slangc-coverage-trend.html', 'slangc trend') + '</p>'
    write(output / 'reports/latest/index.html', page('Latest Slang coverage', navigation))
    # Preserve the native report entry URLs used by the existing dashboard.
    for os_name in ('linux', 'macos', 'windows'):
        for suffix, target in (('', 'new/full/index.html'), ('/slangc', '../new/slangc/index.html')):
            if os_name == "windows" and not windows_available:
                write(output / f'reports/latest/{os_name}{suffix}/index.html',
                      page("Windows coverage unavailable", "<p>No Windows result was collected for this report.</p>"))
                continue
            write(output / f'reports/latest/{os_name}{suffix}/index.html', page('Current coverage',
                  '<meta http-equiv="refresh" content="0;url=' + target + '"><p>'
                  + link(target, 'Open current report') + '</p>'))
    write(output / 'reports/index.html', page('Slang coverage', '<p>' + link('latest/index.html', 'Current coverage') + '</p>'))
    dashboard = output / 'index.html'
    text = dashboard.read_text(encoding="utf-8")
    banner = '<p>' + link('reports/latest/index.html', 'All current platform and merged reports') + '</p>'
    text, count = re.subn(r'(<body\b[^>]*>)', lambda m: m[0] + banner, text, count=1, flags=re.I)
    if not count:
        raise ValueError('Dashboard is missing its body element')
    write(dashboard, text)

    write(output / "reports/publication.json", json.dumps({"report_commit": revision}) + "\n")

    files = list(regular_files(output))
    total = sum(p.stat().st_size for p in files)
    # Conservative allowance for GNU tar headers, long names, and 512-byte padding.
    entries = sum(1 for _ in output.rglob('*')) + 1
    archive_bound = total + entries * 4096 + 10240
    print(f'Pages content: {total:,} bytes in {len(files):,} files; tar upper bound: {archive_bound:,} bytes')
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(
                f"Pages content: **{total:,} bytes** / {max_bytes:,} byte budget.\n\n"
                f"Conservative tar bound: {archive_bound:,} bytes.\n"
            )
    if total >= WARN_CONTENT_BYTES:
        print(
            f"::warning::Pages content is {total:,} bytes, above the "
            f"{WARN_CONTENT_BYTES:,} byte warning threshold; "
            "review growth before the publication budget is exhausted."
        )
    if total > max_bytes or archive_bound >= MAX_ARCHIVE_BYTES:
        raise ValueError('Pages size budget exceeded; reduce published views before uploading')
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    try:
        stage(args.source, args.output, args.revision)
    except ValueError as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
