#!/usr/bin/env bash
set -euo pipefail

# Require bash 4+ for associative arrays
if [ "${BASH_VERSINFO:-0}" -lt 4 ]; then
    echo "Error: This script requires bash 4 or later"
    echo "Current version: $BASH_VERSION"
    echo ""
    echo "On macOS, install with: brew install bash"
    echo "Then run with: /usr/local/bin/bash $0 $@"
    exit 1
fi

# Cull old coverage reports based on retention policy:
# - Keep all reports from last 14 days
# - Keep one report per week for days 15-42 (weeks 3-6)
# - Keep one report per month for older reports
#
# Usage: ./cull-old-reports.sh [--dry-run]

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "=== DRY RUN MODE - No files will be deleted ==="
fi

REPORTS_DIR="reports/history"
TODAY=$(date +%s)

# Calculate time boundaries
TWO_WEEKS_AGO=$((TODAY - 14 * 86400))
SIX_WEEKS_AGO=$((TODAY - 42 * 86400))

echo "Analyzing reports in $REPORTS_DIR..."
echo "Current date: $(date -r "$TODAY" '+%Y-%m-%d')"
echo "Two weeks ago: $(date -r "$TWO_WEEKS_AGO" '+%Y-%m-%d')"
echo "Six weeks ago: $(date -r "$SIX_WEEKS_AGO" '+%Y-%m-%d')"
echo ""

# Arrays to track which reports to keep
declare -A keep_reports
declare -A week_buckets
declare -A month_buckets

# Find all report directories
if [[ ! -d "$REPORTS_DIR" ]]; then
    echo "Error: $REPORTS_DIR does not exist"
    exit 1
fi

# Process each report directory
for report_dir in "$REPORTS_DIR"/20*; do
    if [[ ! -d "$report_dir" ]]; then
        continue
    fi

    dirname=$(basename "$report_dir")

    # Extract date from directory name (format: YYYY-MM-DD-commit)
    if [[ "$dirname" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})- ]]; then
        year="${BASH_REMATCH[1]}"
        month="${BASH_REMATCH[2]}"
        day="${BASH_REMATCH[3]}"
        date_str="$year-$month-$day"

        # Convert to Unix timestamp
        report_timestamp=$(date -j -f "%Y-%m-%d" "$date_str" +%s 2>/dev/null || echo 0)

        if [[ $report_timestamp -eq 0 ]]; then
            echo "Warning: Could not parse date from $dirname, keeping it"
            keep_reports["$dirname"]=1
            continue
        fi

        age_days=$(( (TODAY - report_timestamp) / 86400 ))

        # Decide retention based on age
        if [[ $report_timestamp -gt $TWO_WEEKS_AGO ]]; then
            # Keep all reports from last 14 days
            keep_reports["$dirname"]=1
            echo "KEEP (last 2 weeks): $dirname (age: ${age_days}d)"
        elif [[ $report_timestamp -gt $SIX_WEEKS_AGO ]]; then
            # Keep one per week for weeks 3-6
            # Calculate ISO week number
            week_key=$(date -j -f "%Y-%m-%d" "$date_str" "+%Y-W%V" 2>/dev/null || echo "unknown")

            if [[ -z "${week_buckets[$week_key]:-}" ]] || [[ "$dirname" > "${week_buckets[$week_key]}" ]]; then
                # Keep the most recent report from this week
                week_buckets["$week_key"]="$dirname"
            fi
            echo "WEEKLY bucket [$week_key]: $dirname (age: ${age_days}d)"
        else
            # Keep one per month for older reports
            month_key="$year-$month"

            if [[ -z "${month_buckets[$month_key]:-}" ]] || [[ "$dirname" > "${month_buckets[$month_key]}" ]]; then
                # Keep the most recent report from this month
                month_buckets["$month_key"]="$dirname"
            fi
            echo "MONTHLY bucket [$month_key]: $dirname (age: ${age_days}d)"
        fi
    else
        echo "Warning: Could not parse date from $dirname, keeping it"
        keep_reports["$dirname"]=1
    fi
done

# Add weekly and monthly representatives to keep list
for dirname in "${week_buckets[@]}"; do
    keep_reports["$dirname"]=1
done

for dirname in "${month_buckets[@]}"; do
    keep_reports["$dirname"]=1
done

echo ""
echo "=== Retention Summary ==="
echo "Total reports to keep: ${#keep_reports[@]}"
echo ""

# Now delete reports not in the keep list
deleted_count=0
kept_count=0

for report_dir in "$REPORTS_DIR"/20*; do
    if [[ ! -d "$report_dir" ]]; then
        continue
    fi

    dirname=$(basename "$report_dir")

    if [[ -z "${keep_reports[$dirname]:-}" ]]; then
        # This report should be deleted
        size=$(du -sh "$report_dir" 2>/dev/null | cut -f1)
        if $DRY_RUN; then
            echo "Would DELETE: $dirname (size: $size)"
        else
            echo "DELETING: $dirname (size: $size)"
            rm -rf "$report_dir"
        fi
        deleted_count=$((deleted_count + 1))
    else
        kept_count=$((kept_count + 1))
    fi
done

echo ""
echo "=== Final Results ==="
echo "Reports kept: $kept_count"
echo "Reports deleted: $deleted_count"

if $DRY_RUN; then
    echo ""
    echo "This was a dry run. Run without --dry-run to actually delete files."
fi
