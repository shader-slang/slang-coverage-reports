#!/usr/bin/env python3

import subprocess
import json
import re
from pathlib import Path

def get_coverage_commits():
    """Get all commits with coverage reports."""
    result = subprocess.run(
        ['git', 'log', '--all', '--grep=multi-platform coverage', '--format=%H %s'],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip().split('\n')

def extract_date_from_message(message):
    """Extract date from commit message."""
    match = re.search(r'(\d{4}-\d{2}-\d{2})', message)
    return match.group(1) if match else None

def extract_slang_commit_from_message(message):
    """Extract Slang commit hash from commit message."""
    match = re.search(r'\(([0-9a-f]{7,40})\)', message)
    return match.group(1) if match else None

def get_linux_coverage(commit_hash, date=None, slang_commit=None):
    """Get Linux coverage data from a specific commit."""
    candidate_paths = []
    if date and slang_commit:
        candidate_paths.append(
            f'reports/history/{date}-{slang_commit}/linux/coverage-summary.json'
        )
    candidate_paths.append('reports/latest/linux/coverage-summary.json')

    for linux_file in candidate_paths:
        try:
            result = subprocess.run(
                ['git', 'show', f'{commit_hash}:{linux_file}'],
                capture_output=True,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            return data
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue

    # Fallback: choose the lexicographically last matching report if we
    # couldn't resolve a specific path.
    result = subprocess.run(
        ['git', 'ls-tree', '-r', commit_hash, '--name-only'],
        capture_output=True,
        text=True,
        check=True
    )
    linux_files = sorted(
        f for f in result.stdout.split('\n')
        if 'linux/coverage-summary.json' in f and f.startswith('reports/')
    )
    if not linux_files:
        return None

    linux_file = linux_files[-1]
    try:
        result = subprocess.run(
            ['git', 'show', f'{commit_hash}:{linux_file}'],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        return data
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None

def load_current_linux_coverage():
    """Load Linux coverage data from the checked-out report data export."""
    data_file = Path('reports/coverage-data.json')
    if not data_file.exists():
        return {}

    try:
        records = json.loads(data_file.read_text())
    except json.JSONDecodeError:
        return {}

    daily_data = {}
    for record in records:
        if record.get('platform') != 'linux':
            continue
        if 'slangc_line_coverage' not in record:
            continue

        date = record.get('date')
        if date:
            daily_data[date] = record

    return daily_data

def main():
    print("Extracting Linux slangc compiler pipeline coverage data...")

    # Collect all daily coverage data
    daily_data = load_current_linux_coverage()

    commits = get_coverage_commits()
    for commit_line in commits:
        if not commit_line:
            continue

        parts = commit_line.split(' ', 1)
        if len(parts) != 2:
            continue

        commit_hash, message = parts
        date = extract_date_from_message(message)
        slang_commit = extract_slang_commit_from_message(message)

        if not date:
            continue

        coverage = get_linux_coverage(commit_hash, date, slang_commit)
        if coverage and date not in daily_data:
            # Use git history to backfill older entries that have been culled
            # from the checked-out reports/history directory.
            if 'slangc_line_coverage' in coverage:
                daily_data[date] = coverage

    # Output CSV
    print("\nDate,Line Coverage %,Lines Hit,Lines Found,Region Coverage %,Function Coverage %,Branch Coverage %")

    for date in sorted(daily_data.keys()):
        data = daily_data[date]
        print(f"{date},"
              f"{data.get('slangc_line_coverage', 'N/A')},"
              f"{data.get('slangc_lines_hit', 'N/A')},"
              f"{data.get('slangc_lines_found', 'N/A')},"
              f"{data.get('slangc_region_coverage', 'N/A')},"
              f"{data.get('slangc_function_coverage', 'N/A')},"
              f"{data.get('slangc_branch_coverage', 'N/A')}")

if __name__ == '__main__':
    main()
