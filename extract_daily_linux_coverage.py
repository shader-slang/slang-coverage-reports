#!/usr/bin/env python3

import subprocess
import json
import re
from datetime import datetime

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

def main():
    print("Extracting Linux coverage data from git history...")

    # Collect all daily coverage data
    daily_data = {}

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
            # Take first occurrence (most recent in git log output)
            daily_data[date] = coverage

    # Output CSV
    print("\nDate,Line Coverage %,Lines Hit,Lines Found,Region Coverage %,Function Coverage %,Branch Coverage %")

    for date in sorted(daily_data.keys()):
        data = daily_data[date]
        print(f"{date},"
              f"{data.get('line_coverage', 'N/A')},"
              f"{data.get('lines_hit', 'N/A')},"
              f"{data.get('lines_found', 'N/A')},"
              f"{data.get('region_coverage', 'N/A')},"
              f"{data.get('function_coverage', 'N/A')},"
              f"{data.get('branch_coverage', 'N/A')}")

if __name__ == '__main__':
    main()
